"""
Scheduler jobs module.

Contains scheduled jobs for self-ping, kill-switch restoration, order count monitoring,
quick position auto-close, auto stop-loss, account overview logging, and order history updates.

This module is PEP 8 compliant, documented, and includes light optimizations such as
selective field fetching and reduced repeated DB hits where safe.

Keep variable names and logic intact to preserve compatibility with the rest of your codebase.
"""

from datetime import datetime
import logging
import time
from typing import List, Tuple, Optional

import pytz
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import JsonResponse

from account.models import (
    Control

)
from reports.models import (
    DhanKillProcessLog,
    DailyAccountOverview,
    OrderHistoryLog,

)

from dhanhq import dhanhq

# Configure module logger
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# get user model
User = get_user_model()


# ---------- Utility / Logging -------------------------------------------------


def log_performance(job_name: str, start_time: float, end_time: float) -> None:
    """
    Log elapsed time for a job.

    Args:
        job_name: Name of the job.
        start_time: Start time in seconds (time.time()).
        end_time: End time in seconds (time.time()).
    """
    duration = end_time - start_time
    logger.info("Job '%s' executed in %.4f seconds.", job_name, duration)
    print(f"INFO: Job '{job_name}' executed in {duration:.4f} seconds.")


# ---------- Health / maintenance jobs --------------------------------------


def self_ping() -> None:
    """
    Ping the application root to keep dynos/containers awake and log the response.

    This is a simple healthcheck request, prints and logs the status code.
    """
    try:
        response = requests.get("https://tradewiz.onrender.com/")
        logger.info("Health check response: %s", response.status_code)
        print(f"INFO: Health check response: {response.status_code}")
    except Exception as exc:
        logger.exception("Error in self_ping: %s", exc)
        print(f"ERROR: Error in self_ping: {exc}")


def restore_user_kill_switches() -> None:
    """
    Reset kill switch flags and Order Limit Seconds for all controls and active users.

    Sets kill_switch_1, kill_switch_2 to False, status True, last_order_count to 0,
    and clears is_superuser for active users.

    Also resets Control.order_limit_second to Control.default_order_limit_second for all
    Control rows.
    """
    try:
        active_users_qs = User.objects.filter(is_active=True)
        # Bulk update user boolean fields (Django 4+ supports update on QuerySet)
        count = active_users_qs.update(
            kill_switch_1=False,
            kill_switch_2=False,
            status=True,
            last_order_count=0,
            is_superuser=False,
        )

        # Reset controls
        all_controls = Control.objects.all()
        for control in all_controls:
            control.order_limit_second = control.default_order_limit_second
            control.save(update_fields=["order_limit_second"])

        msg = f"INFO: Reset kill switches for {count} users."
        logger.info(msg)
        print(msg)
    except Exception as exc:
        logger.exception("Error in restore_user_kill_switches: %s", exc)
        print(f"ERROR: Error in restore_user_kill_switches: {exc}")


# ---------- Order count / kill switch monitoring ---------------------------


def auto_order_count_monitoring_process() -> JsonResponse:
    """
    Monitor order counts for users and activate kill switches based on Control thresholds.

    Runs only Monday-Friday, 9:00-15:59 IST. Returns JsonResponse indicating outcome.
    """
    start_time = time.time()
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)
    print(f"Current date and time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print("STARTING KILL SWITCH ON ORDER COUNT LIMIT PROCESS......")

    if not (now.weekday() < 5 and (9 <= now.hour < 16)):
        print("INFO: Current time is outside of the scheduled range.")
        return JsonResponse({"status": "skipped", "message": "Outside scheduled range"})

    
    try:
        # Only fetch active users with status True to reduce iteration
        active_users = User.objects.filter(is_active=True, status=True).only(
            "username", "dhan_client_id", "dhan_access_token", "kill_switch_1", "kill_switch_2"
        )

        for user in active_users:
            try:
                dhan_client_id = user.dhan_client_id
                dhan_access_token = user.dhan_access_token
                print(
                    " KILL SWITCH ON ORDER COUNT LIMIT PROCESS  : Processing user: %s, Client ID: %s"
                    % (user.username, dhan_client_id)
                )

                dhan = dhanhq(dhan_client_id, dhan_access_token)
                order_list = dhan.get_order_list()
                traded_order_count = get_traded_order_count(order_list)
                print("traded_order_counttraded_order_count", traded_order_count)

                if traded_order_count > 0:
                    control_data = Control.objects.filter(user=user).first()
                    if control_data:
                        print(f"Handling order limits for user: {user.username}")
                        handle_order_limits(
                            user, dhan, order_list, traded_order_count, control_data, dhan_access_token
                        )
                    else:
                        print(f"INFO: No control data found for user: {user.username}")
                else:
                    print(f"INFO: No Orders Placed in  user: {user.username}")

            except Exception as exc:
                logger.exception("Error processing user %s: %s", getattr(user, "username", "unknown"), exc)
                print(f"ERROR: Error processing user {getattr(user, 'username', 'unknown')}: {exc}")

        elapsed = time.time() - start_time
        log_performance("auto_order_count_monitoring_process", start_time, time.time())
        print("Monitoring process completed successfully.")
        return JsonResponse({"status": "success", "message": "Monitoring process completed"})
    except Exception as exc:
        logger.exception("Error in monitoring process: %s", exc)
        print(f"ERROR: Error in monitoring process: {exc}")
        return JsonResponse({"status": "error", "message": "An error occurred"}, status=500)


def handle_order_limits(
    user,
    dhan,
    order_list,
    traded_order_count: int,
    control_data,
    dhan_access_token: str,
) -> None:
    """
    Evaluate order limits and activate kill switches accordingly.

    Args:
        user: Django user instance.
        dhan: dhanhq client instance.
        order_list: order list response from dhanhq.
        traded_order_count: number of traded orders.
        control_data: Control model instance for the user.
        dhan_access_token: Access token string for API calls.
    """
    print(f"Evaluating order limits for user: {user.username}")
    pending_order_ids, pending_order_count = get_pending_order_list_and_count(order_list)

    if control_data.max_order_count_mode:
        print("control_data.order_limit_second:", control_data.order_limit_second)
        if (
            traded_order_count >= control_data.order_limit_first
            and traded_order_count < control_data.order_limit_second
            and not user.kill_switch_1
            and not user.kill_switch_2
        ):
            print(
                f"WARNING: Order Limit First exceeded for user {user.username}: Limit = {control_data.order_limit_first}, Traded = {traded_order_count}"
            )
            activate_kill_switch(user, dhan_access_token, traded_order_count, switch="kill_switch_1")
        elif (
            traded_order_count >= control_data.order_limit_second
            and user.kill_switch_1
            and not user.kill_switch_2
        ):
            print(
                f"WARNING: Order Limit Second exceeded for user {user.username}: Limit = {control_data.order_limit_second}, Traded = {traded_order_count}"
            )
            activate_kill_switch(user, dhan_access_token, traded_order_count, switch="kill_switch_2")
        elif user.kill_switch_2:
            print(
                f"INFO: Kill Switch 2 Activated for {user.username}: Count = {traded_order_count}, Limit = {control_data.order_limit_first}"
            )
        else:
            print(
                f"INFO: Order count within limits for user {user.username}: Count = {traded_order_count}, Limit = {control_data.order_limit_first}"
            )


def get_pending_order_list_and_count(order_list: dict) -> Tuple[List, int]:
    """
    Return list of pending order IDs and count.

    Args:
        order_list: Response dict from dhanhq.get_order_list()

    Returns:
        Tuple of (pending_order_ids, pending_order_count)
    """
    if not isinstance(order_list, dict) or "data" not in order_list:
        return [], 0
    pending_orders = [order for order in order_list["data"] if order.get("orderStatus") == "PENDING"]
    pending_order_ids = [order.get("orderId") for order in pending_orders]
    return pending_order_ids, len(pending_order_ids)


def activate_kill_switch(user, access_token: str, traded_order_count: int, switch: str) -> None:
    """
    Call the external killSwitch API and update user flags and logs accordingly.

    Args:
        user: Django user instance.
        access_token: API access token for headers.
        traded_order_count: Number of traded orders triggering switch.
        switch: Which switch to activate ("kill_switch_1" or "kill_switch_2").
    """
    url = "https://api.dhan.co/killSwitch?killSwitchStatus=ACTIVATE"
    headers = {"Accept": "application/json", "Content-Type": "application/json", "access-token": access_token}

    try:
        response = requests.post(url, headers=headers, timeout=10)
        if response.status_code == 200:
            DhanKillProcessLog.objects.create(user=user, log=response.json(), order_count=traded_order_count)

            if switch == "kill_switch_1":
                user.kill_switch_1 = True
                print(f"INFO: Kill switch 1 activated for user: {user.username}")
            elif switch == "kill_switch_2":
                user.status = False
                user.kill_switch_2 = True
                print(f"INFO: Kill switch 2 activated for user: {user.username}")

            user.save(update_fields=["kill_switch_1", "kill_switch_2", "status"])
        else:
            msg = f"ERROR: Failed to activate kill switch for user {user.username}: Status code {response.status_code}"
            logger.error(msg)
            print(msg)
    except requests.RequestException as exc:
        logger.exception("Error activating kill switch for user %s: %s", user.username, exc)
        print(f"ERROR: Error activating kill switch for user {user.username}: {exc}")


# ---------- Quick-exit (auto close positions) --------------------------------


def autoclosePositionProcess() -> JsonResponse:
    """
    Detect CANCELLED STOP_LOSS SELL transactions and attempt to place a market SELL
    to close positions quickly.

    Operates Monday-Friday, 9:00-15:59 IST. Returns JsonResponse with status.
    """
    start_time = time.time()
    print("AUTO CLOSE POSITIONS PROCESS RUNNING....")
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)
    print(f"Current date and time: {now.strftime('%Y-%m-%d %H:%M:%S')}")

    if not (now.weekday() < 5 and (9 <= now.hour < 16)):
        print("INFO: Current time is outside of the scheduled range.")
        log_performance("autoclosePositionProcess", start_time, time.time())
        return JsonResponse({"status": "skipped", "message": "Outside scheduled range"})

    try:
        print("STARTING AUTO CLOSE POSITION MONITORING PROCESS...!")
        # Only select users that have quick_exit enabled to reduce work
        active_users = User.objects.filter(is_active=True, status=True, quick_exit=True).only(
            "username", "dhan_client_id", "dhan_access_token"
        )

        if not active_users.exists():
            print("No User Found.(May be Killed Already/Not Active)")
            print("Auto Quick Exit process completed successfully.")
            log_performance("autoclosePositionProcess", start_time, time.time())
            return JsonResponse({"status": "success", "message": "Monitoring process completed"})

        for user in active_users:
            try:
                dhan_client_id = user.dhan_client_id
                dhan_access_token = user.dhan_access_token
                print(
                    "STARTING QUICK CLOSE POSITION : Processing user: %s, Client ID: %s"
                    % (user.username, dhan_client_id)
                )

                control_data = Control.objects.filter(user=user).first()
                dhan = dhanhq(dhan_client_id, dhan_access_token)
                order_list = dhan.get_order_list()
                traded_order_count = get_traded_order_count(order_list)
                if traded_order_count > 0:
                    latest_entry = order_list["data"][0]
                    if (
                        latest_entry.get("orderType") == "STOP_LOSS"
                        and latest_entry.get("orderStatus") == "CANCELLED"
                        and latest_entry.get("transactionType") == "SELL"
                    ):
                        sl_order_id = latest_entry.get("orderId")
                        symbol = latest_entry.get("tradingSymbol")
                        security_id = latest_entry.get("securityId")
                        client_id = latest_entry.get("dhanClientId")
                        exchange_segment = latest_entry.get("exchangeSegment")
                        quantity = latest_entry.get("quantity")
                        traded_price = float(latest_entry.get("price", 0))
                        print("***************************************************************************")
                        print("LATEST CANCELLED STOPLOSS ENTRY DETECTED          : True")
                        print("QUICK EXIT : SELL ORDER PAYLOAD DATA FOR USER     :", user.username)
                        print("SECURITY ID                                       :", security_id)
                        print("CLIENT ID                                         :", client_id)
                        print("EXCHANGE SEGMENT                                  :", exchange_segment)
                        print("QUANTITY                                          :", quantity)
                        print("TRADE PRICE                                       :", traded_price)
                        print("***************************************************************************")

                        try:
                            sellOrderResponse = dhan.place_order(
                                security_id=security_id,
                                exchange_segment=exchange_segment,
                                transaction_type="SELL",
                                quantity=quantity,
                                order_type="MARKET",
                                product_type="INTRADAY",
                                price=0,
                            )

                            print("Sell Order Response:", sellOrderResponse)

                            with transaction.atomic():
                                DhanKillProcessLog.objects.create(user=user, log=sellOrderResponse, order_count=quantity)

                                if sellOrderResponse.get("status") == "failure":
                                    error_message = sellOrderResponse.get("remarks", {}).get("error_message", "Unknown error")
                                    error_code = sellOrderResponse.get("remarks", {}).get("error_code", "Unknown code")

                                    DhanKillProcessLog.objects.create(
                                        user=user,
                                        log={"error_message": error_message, "error_code": error_code},
                                        order_count=0,
                                    )

                                    print("Order failed:", error_message)

                            print("INFO: Position Closing Executed Successfully..!")
                        except Exception as exc:
                            DhanKillProcessLog.objects.create(
                                user=user, log={"error_message": str(exc), "error_code": "Exception"}, order_count=0
                            )
                            logger.exception("An error occurred while executing the sell order for %s: %s", user.username, exc)
                            print("An error occurred while executing the sell order:", str(exc))
                    else:
                        print(f"INFO: No Open Order for User {user.username}")
                else:
                    print(f"INFO: No Open Order for User :{user.username}")

            except Exception as exc:
                logger.exception("Error processing user %s: %s", getattr(user, "username", "unknown"), exc)
                print(f"ERROR: Error processing user {getattr(user, 'username', 'unknown')}: {exc}")

        print("Auto Quick Exit process completed successfully.")
        log_performance("autoclosePositionProcess", start_time, time.time())
        return JsonResponse({"status": "success", "message": "Monitoring process completed"})

    except Exception as exc:
        logger.exception("Error in stoploss monitoring process: %s", exc)
        print(f"ERROR: Error in stoploss monitoring process: {exc}")
        log_performance("autoclosePositionProcess", start_time, time.time())
        return JsonResponse({"status": "error", "message": "An error occurred"}, status=500)


def get_traded_order_count(order_list: dict) -> int:
    """
    Return number of orders with orderStatus == 'TRADED' in order_list.

    Args:
        order_list: Response dict from dhanhq.get_order_list()

    Returns:
        Count of traded orders.
    """
    if "data" not in order_list or not isinstance(order_list["data"], list) or not order_list["data"]:
        return 0

    traded_count = len([order for order in order_list["data"] if order.get("orderStatus") == "TRADED"])
    return traded_count if traded_count else 0


def get_order_count(order_list: dict) -> int:
    """
    Return total number of orders present in order_list data.

    Args:
        order_list: Response dict from dhanhq.get_order_list()

    Returns:
        Integer count of orders.
    """
    if "data" not in order_list or not isinstance(order_list["data"], list) or not order_list["data"]:
        return 0

    traded_count = len(order_list["data"])
    return traded_count if traded_count else 0

# ---------- Auto Stop-loss (Modified) -----------------------------------

def autoStopLossLotControlProcess() -> JsonResponse:
    """
    Automatically place stop-loss SELL orders after a BUY was TRADED.
    
    Logic:
    1. If pending SL order exists → Place NEW SL order for new trade
    2. If no pending SL order → Place NEW SL order
    
    Runs Monday-Friday, 9:00-15:59 IST.
    """
    start_time = time.time()
    print("Auto Stop Loss Process Running")
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)
    print(f"Current date and time: {now.strftime('%Y-%m-%d %H:%M:%S')}")

    if not (now.weekday() < 5 and (9 <= now.hour < 16)):
        print("INFO: Current time is outside of the scheduled range.")
        log_performance("autoStopLossLotControlProcess", start_time, time.time())
        return JsonResponse({"status": "skipped", "message": "Outside scheduled range"})

    try:
        active_users = User.objects.filter(is_active=True, status=True, auto_stop_loss=True).only(
            "username", "dhan_client_id", "dhan_access_token"
        )
        print("STARTING AUTO STOP LOSS MONITORING PROCESS......................!")

        for user in active_users:
            try:
                if user.auto_stop_loss:
                    dhan_client_id = user.dhan_client_id
                    dhan_access_token = user.dhan_access_token
                    print(
                        "AUTO STOP LOSS MONITORING PROCESS : Processing user: %s, Client ID: %s"
                        % (user.username, dhan_client_id)
                    )

                    control_data = Control.objects.filter(user=user).first()
                    if not control_data:
                        print(f"INFO: No control data found for user: {user.username}")
                        continue

                    stoploss_parameter = float(control_data.stoploss_parameter)

                    dhan = dhanhq(dhan_client_id, dhan_access_token)
                    order_list = dhan.get_order_list()

                    if order_list.get("data"):
                        latest_entry = order_list["data"][0]
                        if latest_entry.get("transactionType") == "BUY" and latest_entry.get("orderStatus") == "TRADED":
                            security_id = latest_entry.get("securityId")
                            traded_symbol = latest_entry.get("tradingSymbol")
                            client_id = latest_entry.get("dhanClientId")
                            exchange_segment = latest_entry.get("exchangeSegment")
                            quantity = latest_entry.get("quantity")
                            traded_price = float(latest_entry.get("price", 0))

                            # Calculate SL price for this trade
                            sl_price, sl_trigger = calculateslprice(
                                traded_price, stoploss_parameter, control_data.stoploss_type, traded_symbol, quantity
                            )

                            print("***************************************************************************")
                            print("SYMBOL                                             :", traded_symbol)
                            print("AUTO STOP LOSS PROCESS FOR USER                    :", user.username)
                            print("TRADE PRICE                                        :", traded_price)
                            print("SL PRICE                                           :", sl_price)
                            print("TRIGGER PRICE                                      :", sl_trigger)
                            print(f"SECURITY ID                                       : {security_id}")
                            print(f"CLIENT ID                                         : {client_id}")
                            print(f"EXCHANGE SEGMENT                                  : {exchange_segment}")
                            print(f"QUANTITY                                          : {quantity}")
                            print("***************************************************************************")

                            try:
                                # Check if any pending SL order exists
                                pending_sl_orders = get_pending_order_filter_dhan(order_list)

                                if pending_sl_orders:
                                    # Scenario 1: Pending SL exists → Place NEW SL order for new trade
                                    print(f"INFO: PENDING SL ORDER EXISTS. PLACING NEW STOP LOSS ORDER FOR : {user.username}")
                                    
                                    stoploss_response = dhan.place_order(
                                        security_id=security_id,
                                        exchange_segment=exchange_segment,
                                        transaction_type="SELL",
                                        quantity=quantity,
                                        order_type="STOP_LOSS",
                                        product_type="INTRADAY",
                                        price=sl_price,
                                        trigger_price=sl_trigger,
                                    )

                                    DhanKillProcessLog.objects.create(
                                        user=user, 
                                        log=stoploss_response, 
                                        order_count=quantity
                                    )

                                    if stoploss_response.get("status") == "failure":
                                        error_message = stoploss_response.get("remarks", {}).get("error_message", "Unknown error")
                                        error_code = stoploss_response.get("remarks", {}).get("error_code", "Unknown code")
                                        DhanKillProcessLog.objects.create(
                                            user=user,
                                            log={"error_message": error_message, "error_code": error_code},
                                            order_count=0,
                                        )
                                        print("Stop Loss Order failed:", error_message)
                                    else:
                                        print("INFO: NEW STOP LOSS ORDER PLACED SUCCESSFULLY..!")

                                    print("INFO: STOPLOSS ORDER RESPONSE:", stoploss_response)

                                else:
                                    # Scenario 2: No pending SL → Place NEW SL order
                                    print(f"INFO: NO PENDING SL ORDER. PLACING NEW STOP LOSS ORDER FOR : {user.username}")
                                    
                                    stoploss_response = dhan.place_order(
                                        security_id=security_id,
                                        exchange_segment=exchange_segment,
                                        transaction_type="SELL",
                                        quantity=quantity,
                                        order_type="STOP_LOSS",
                                        product_type="INTRADAY",
                                        price=sl_price,
                                        trigger_price=sl_trigger,
                                    )

                                    DhanKillProcessLog.objects.create(
                                        user=user, 
                                        log=stoploss_response, 
                                        order_count=quantity
                                    )

                                    if stoploss_response.get("status") == "failure":
                                        error_message = stoploss_response.get("remarks", {}).get("error_message", "Unknown error")
                                        error_code = stoploss_response.get("remarks", {}).get("error_code", "Unknown code")
                                        DhanKillProcessLog.objects.create(
                                            user=user,
                                            log={"error_message": error_message, "error_code": error_code},
                                            order_count=0,
                                        )
                                        print("Stop Loss Order failed:", error_message)
                                    else:
                                        print("INFO: STOP LOSS ORDER PLACED SUCCESSFULLY..!")

                                    print("INFO: STOPLOSS ORDER RESPONSE:", stoploss_response)

                            except Exception as exc:
                                DhanKillProcessLog.objects.create(
                                    user=user, 
                                    log={"error_message": str(exc), "error_code": "Exception"}, 
                                    order_count=0
                                )
                                logger.exception("An error occurred while processing the stop loss order for %s: %s", user.username, exc)
                                print("An error occurred while processing the stop loss order:", str(exc))
                        else:
                            print(f"INFO: No Recent BUY Order found for User {user.username}")
                    else:
                        print(f"INFO: No Recent Order found for User {user.username}")
                else:
                    print(f"WARNING: Auto SL Disabled for User : {user.username}")
            except Exception as exc:
                logger.exception("ERROR: Error processing user %s: %s", getattr(user, "username", "unknown"), exc)
                print(f"ERROR: Error processing user {getattr(user, 'username', 'unknown')}: {exc}")

        print("INFO: No User Found.(May be Killed Already/Not Active)")
        print("INFO: Auto Stoploss Monitoring process completed successfully.")
        log_performance("autoStopLossLotControlProcess", start_time, time.time())
        return JsonResponse({"status": "success", "message": "Monitoring process completed"})
    except Exception as exc:
        logger.exception("ERROR: Error in stoploss monitoring process: %s", exc)
        print(f"ERROR: Error in stoploss monitoring process: {exc}")
        return JsonResponse({"status": "error", "message": "An error occurred"}, status=500)


def calculateslprice(traded_price: float, stoploss_parameter: float, stoploss_type: str, traded_symbol: str, quantity: int) -> Tuple[float, float]:
    """
    Calculate stop-loss price and trigger based on type and slippage.

    Arguments follow original names to preserve compatibility.
    """
    if stoploss_type == "percentage":
        sl_price = traded_price * (1 - stoploss_parameter / 100)
    elif stoploss_type == "points":
        sl_price = traded_price - stoploss_parameter
    elif stoploss_type == "price":
        # integer division similar to original code
        actual_stoploss_parameter = stoploss_parameter // quantity
        sl_price = traded_price - actual_stoploss_parameter
    else:
        # fallback
        sl_price = traded_price

    slippage = float(getattr(settings, "TRIGGER_SLIPPAGE", 0.05))
    try:
        sl_price = round(sl_price / slippage) * slippage
    except Exception:
        # avoid zero division and other rounding issues
        sl_price = round(sl_price, 2)

    sl_trigger = sl_price + slippage * 20
    sl_price = round(sl_price, 2)
    sl_trigger = round(sl_trigger, 2)

    return sl_price, sl_trigger


def get_pending_order_filter_dhan(response: dict):
    """
    Return list of pending SELL orders from dhanhq response.

    Returns False if none found, 0 if response invalid, otherwise list.
    """
    if not isinstance(response, dict) or "data" not in response:
        return 0

    pending_sl_orders = [
        order for order in response["data"]
        if order.get("orderStatus") == "PENDING" and order.get("transactionType") == "SELL"
    ]

    if not pending_sl_orders:
        return False

    return pending_sl_orders



# ---------- Daily / Order history logging ---------------------------------


def check_and_update_daily_account_overview() -> None:
    """
    Create DailyAccountOverview entries for users when order counts change or at market open.
    """
    print("INFO: ACCOUNT OVERVIEW PROCESS RUNNING ....!")
    ist = pytz.timezone("Asia/Kolkata")
    current_time = datetime.now(ist)
    today = current_time.date()
    current_hour = current_time.hour
    is_first_run = current_hour == 9
    is_last_run = current_hour == 15

    is_weekday_9am = current_time.weekday() < 5 and current_time.hour == 9 and current_time.minute == 0

    active_users = User.objects.filter(is_active=True).only("username", "dhan_client_id", "dhan_access_token", "last_order_count")
    for user in active_users:
        try:
            dhan_client_id = user.dhan_client_id
            dhan_access_token = user.dhan_access_token

            dhan = dhanhq(dhan_client_id, dhan_access_token)

            order_list = dhan.get_order_list() or {}
            actual_order_count = get_traded_order_count(order_list)

            if user.last_order_count != actual_order_count:
                user.last_order_count = actual_order_count
                user.save(update_fields=["last_order_count"])
                print(f"INFO: Order count changed for {user.username}. Executing update process.")

                # trigger update on even trades or at 9:00 AM weekday
                if (actual_order_count and actual_order_count % 2 == 0) or is_weekday_9am:
                    # Small delay before fetching funds to let external API settle
                    time.sleep(10)
                    fund_data = dhan.get_fund_limits() or {}
                    position_data = dhan.get_positions() or {}

                    total_expense = actual_order_count * float(getattr(settings, "BROKERAGE_PARAMETER", 0.0))
                    total_realized_profit = sum(
                        position.get("realizedProfit", 0) for position in (position_data.get("data", []) if position_data else [])
                    )
                    opening_balance = float(fund_data.get("data", {}).get("sodLimit", 0.0)) if fund_data else 0.0
                    closing_balance = float(fund_data.get("data", {}).get("availabelBalance", 0.0)) if fund_data else 0.0
                    actual_profit = total_realized_profit - total_expense

                    day_open = False
                    if is_first_run or is_weekday_9am:
                        day_open = True

                    day_close = is_last_run

                    DailyAccountOverview.objects.create(
                        user=user,
                        opening_balance=opening_balance,
                        pnl_status=total_realized_profit,
                        actual_profit=actual_profit,
                        expenses=total_expense,
                        closing_balance=closing_balance,
                        order_count=actual_order_count,
                        day_open=day_open,
                        day_close=day_close,
                    )

                    # Update daily goal report if present
                    try:
                        from account.models import DailyGoalReport  # imported lazily to avoid circular imports
                        daily_goal_data = DailyGoalReport.objects.filter(user=user, date=today).first()
                        if daily_goal_data:
                            daily_goal_data.progress = actual_profit
                            if daily_goal_data.gained_amount <= actual_profit:
                                daily_goal_data.is_achieved = True
                            daily_goal_data.save(update_fields=["progress", "is_achieved"])
                            print(f"INFO: DailyGoalReport updated successfully for {user.username}")
                        else:
                            print("INFO:No DailyGoalReport found for the given user and date.")
                    except Exception:
                        # If DailyGoalReport missing or import fails, just log and continue
                        logger.debug("DailyGoalReport not available or error updating it.", exc_info=True)

                    print(f"INFO: DailyAccountOverview updated successfully for {user.username}")
            else:
                print(f"INFO: No change in order count for {user.username}. No update required.")
        except Exception as exc:
            logger.exception("INFO: Error processing user %s: %s", getattr(user, "username", "unknown"), exc)
            print(f"INFO: Error processing user {getattr(user, 'username', 'unknown')}: {exc}")
            continue


def restore_super_user_after_market() -> None:
    """
    Restore developer admin to superuser after market (called at market close).
    """
    dev_admin = getattr(settings, "DEV_ADMIN", None)
    if not dev_admin:
        print("DEV_ADMIN not set in settings.")
        return

    user = User.objects.filter(username=dev_admin).first()
    if user:
        user.is_superuser = True
        user.save(update_fields=["is_superuser"])
        print(f"INFO: Restored superuser to {dev_admin}")
    else:
        print("Developer admin user not found.")


def update_order_history() -> None:
    """
    Log order history for users. This creates OrderHistoryLog entries summarising
    orders, P&L and balances for the day.
    """
    active_users = User.objects.filter(is_active=True).only("username", "dhan_client_id", "dhan_access_token")
    for user in active_users:
        try:
            dhan_client_id = user.dhan_client_id
            dhan_access_token = user.dhan_access_token
            dhan = dhanhq(dhan_client_id, dhan_access_token)
            order_list = dhan.get_order_list() or {}
            actual_order_count = len(order_list.get("data", []))

            if actual_order_count:
                latest_entry = order_list["data"][0]  # Keep original assumption
                fund_data = dhan.get_fund_limits() or {}
                position_data = dhan.get_positions() or {}

                total_expense = actual_order_count * float(getattr(settings, "BROKERAGE_PARAMETER", 0.0))
                total_realized_profit = sum(
                    position.get("realizedProfit", 0) for position in position_data.get("data", [])
                )

                opening_balance = float(fund_data.get("data", {}).get("sodLimit", 0.0))
                closing_balance = float(fund_data.get("data", {}).get("withdrawableBalance", 0.0))

                actual_profit = total_realized_profit - total_expense

                OrderHistoryLog.objects.create(
                    user=user,
                    order_data=order_list,
                    date=datetime.today().date(),
                    order_count=actual_order_count,
                    profit_loss=actual_profit,
                    eod_balance=closing_balance,
                    sod_balance=opening_balance,
                    expense=total_expense,
                )

                print(f"INFO: OrderHistoryLog updated successfully for {user.username}")
            else:
                print(f"INFO: No orders found for {user.username}. No update required.")
        except Exception as exc:
            logger.exception("INFO: Error processing user %s: %s", getattr(user, "username", "unknown"), exc)
            print(f"INFO: Error processing user {getattr(user, 'username', 'unknown')}: {exc}")
            continue


# ---------- Scheduler setup -----------------------------------------------


def start_scheduler() -> None:
    """
    Configure and start the BackgroundScheduler with all jobs.

    This prints scheduler start activity so you can verify the scheduler is writing.
    """
    scheduler = BackgroundScheduler()
    ist = pytz.timezone("Asia/Kolkata")

    # SELF PING TESTED OK
    scheduler.add_job(self_ping, IntervalTrigger(seconds=180))

    # RESTORE KILL SWITCH BY 9 AM AND 3:30 PM TESTED OK
    scheduler.add_job(
        restore_user_kill_switches,
        CronTrigger(day_of_week="mon-fri", hour=9, minute=0, timezone=ist),
    )
    scheduler.add_job(
        restore_super_user_after_market,
        CronTrigger(day_of_week="mon-fri", hour=15, minute=30, timezone=ist),
    )

    # ORDER COUNT-KILL FEATURE TESTED OK
    scheduler.add_job(auto_order_count_monitoring_process, IntervalTrigger(seconds=2), max_instances=3, replace_existing=True)

    # QUICK EXIT FEATURE TESTED OK
    scheduler.add_job(autoclosePositionProcess, IntervalTrigger(seconds=1), max_instances=3, replace_existing=True)

    # AUTO STOPLOSS FEATURE TESTED OK
    scheduler.add_job(autoStopLossLotControlProcess, IntervalTrigger(seconds=2), max_instances=2, replace_existing=True)

    # HOURLY DATA LOG MONITORING TESTED OK
    scheduler.add_job(check_and_update_daily_account_overview, IntervalTrigger(seconds=15), max_instances=10, replace_existing=True)

    # ORDER DATA LOG MONITORING TESTED OK
    scheduler.add_job(update_order_history, CronTrigger(day_of_week="mon-fri", hour=15, minute=30, timezone=ist))

    # scheduler.start()
    print("INFO: Scheduler started.")
    logger.info("Scheduler started with jobs: %s", scheduler.get_jobs())

    # Ensure scheduler shuts down cleanly at exit
    import atexit

    atexit.register(lambda: shutdown_scheduler(scheduler))


def shutdown_scheduler(scheduler: BackgroundScheduler) -> None:
    """
    Safely shutdown the scheduler (helper used by atexit).
    """
    try:
        scheduler.shutdown(wait=True)
        print("INFO: Scheduler shut down.")
        logger.info("Scheduler shut down.")
    except Exception as exc:
        logger.exception("Error shutting down scheduler: %s", exc)
        print(f"ERROR: Error shutting down scheduler: {exc}")

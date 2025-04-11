from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from django.conf import settings
import requests
import atexit
from django.http import JsonResponse
from django.contrib.auth import get_user_model
from dhanhq import dhanhq
from account.models import Control, DhanKillProcessLog, DailyAccountOverview, TempNotifierTable, slOrderslog, OrderHistoryLog
from datetime import datetime
from django.db.models import F
import pytz
User = get_user_model()

# LOGGER  ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

def log_performance(job_name, start_time, end_time):
    # Calculate the difference (elapsed time)
    duration = end_time - start_time
    logging.info(f"Job '{job_name}' executed in {duration:.4f} seconds.")


# SELF PING TESTED OK ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

def self_ping():
    try:
        response = requests.get('https://tradewiz.onrender.com/')
        print(f"INFO: Health check response: {response.status_code}")
    except Exception as e:
        print(f"ERROR: Error in self_ping: {e}")



# RESTORE KILL ON 9 AND 4 TESTED OK----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

def restore_user_kill_switches():
    active_users = User.objects.filter(is_active=True)
    active_users.update(kill_switch_1=False, kill_switch_2=False, status=True,last_order_count=0, is_superuser = False)
    all_controls = Controls.objects.all()
    for control in all_controls:
        control.peak_order_limit = control.default_peak_order_limit
        control.save()
    print(f"INFO: Reset kill switches for {active_users.count()} users.")


# RESTORE KILL ON 9 AND 4 TESTED OK----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------



# KILL SIWTCH ON ORDER COUNT LIMIT TESTED OK-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

def auto_order_count_monitoring_process():
    ist = pytz.timezone('Asia/Kolkata')
    now =  datetime.now(ist)
    print(f"Current date and time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    if now.weekday() < 5 and (9 <= now.hour < 16):  # Monday to Friday, 9 AM to 4 PM
        try:
            print("STARTING KILL SIWTCH ON ORDER COUNT LIMIT PROCESS......!")
            active_users = User.objects.filter(is_active=True, status=True)
            for user in active_users:
                try:
                    if user:
                        dhan_client_id = user.dhan_client_id
                        dhan_access_token = user.dhan_access_token
                        print(f" KILL SWITCH ON ORDER COUNT LIMIT PROCESS  : Processing user: {user.username}, Client ID: {dhan_client_id}")
                        # Initialize Dhan client
                        dhan = dhanhq(dhan_client_id, dhan_access_token)
                        # Fetch order list
                        order_list = dhan.get_order_list()
                        traded_order_count = get_traded_order_count(order_list)
                        print("traded_order_counttraded_order_count", traded_order_count)
                        if traded_order_count > 0:
                            # Fetch control data
                            control_data = Control.objects.filter(user=user).first()
                            if control_data:
                                print(f"Handling order limits for user: {user.username}")
                                handle_order_limits(user, dhan, order_list, traded_order_count, control_data, dhan_access_token)
                            else:
                                print(f"INFO: No control data found for user: {user.username}")
                        else:
                            print(f"INFO: No Orders Placed in  user: {user.username}")
                    else:
                        print(f"INFO: Kill switch already activated twice for user: {user.username}")

                except Exception as e:
                    print(f"ERROR: Error processing user {user.username}: {e}")

            print("Monitoring process completed successfully.")
            return JsonResponse({'status': 'success', 'message': 'Monitoring process completed'})

        except Exception as e:
            print(f"ERROR: Error in monitoring process: {e}")
            return JsonResponse({'status': 'error', 'message': 'An error occurred'}, status=500)
    else:
        print("INFO: Current time is outside of the scheduled range.")



def handle_order_limits(user, dhan, order_list, traded_order_count, control_data, dhan_access_token):
    print(f"Evaluating order limits for user: {user.username}")
    pending_order_ids, pending_order_count = get_pending_order_list_and_count(order_list)
    if control_data.max_order_count_mode:
        print("control_data.peak_order_limit:", control_data.peak_order_limit)
        if traded_order_count >= control_data.max_order_limit and traded_order_count < control_data.peak_order_limit and not user.kill_switch_1 and not user.kill_switch_2:
            print(f"WARNING: Max order limit exceeded for user {user.username}: Limit = {control_data.max_order_limit}, Traded = {traded_order_count}")
            activate_kill_switch(user, dhan_access_token, traded_order_count, switch="kill_switch_1")
        elif traded_order_count >= control_data.peak_order_limit and user.kill_switch_1 and not user.kill_switch_2:
            print(f"WARNING: Peak order limit exceeded for user {user.username}: Limit = {control_data.peak_order_limit}, Traded = {traded_order_count}")
            activate_kill_switch(user, dhan_access_token, traded_order_count, switch="kill_switch_2")
        elif user.kill_switch_2:
            print(f"INFO: Kill Switch 2 Activated for {user.username}: Count = {traded_order_count}, Limit = {control_data.max_order_limit}")
        else:
            print(f"INFO: Order count within limits for user {user.username}: Count = {traded_order_count}, Limit = {control_data.max_order_limit}")


def get_pending_order_list_and_count(order_list):
    if 'data' not in order_list:
        return [], 0
    pending_orders = [order for order in order_list['data'] if order.get('orderStatus') == 'PENDING']
    pending_order_ids = [order.get('orderId') for order in pending_orders]
    return pending_order_ids, len(pending_order_ids)



def activate_kill_switch(user, access_token, traded_order_count, switch):
    url = 'https://api.dhan.co/killSwitch?killSwitchStatus=ACTIVATE'
    headers = {'Accept': 'application/json', 'Content-Type': 'application/json', 'access-token': access_token}

    try:
        response = requests.post(url, headers=headers)
        if response.status_code == 200:
            DhanKillProcessLog.objects.create(user=user, log=response.json(), order_count=traded_order_count)
            
            if switch == "kill_switch_1":
                user.kill_switch_1 = True
                print(f"INFO: Kill switch 1 activated for user: {user.username}")
            elif switch == "kill_switch_2":
                user.status = False
                user.kill_switch_2 = True

                print(f"INFO: Kill switch 2 activated for user: {user.username}")
            
            user.save()
        else:
            print(f"ERROR: Failed to activate kill switch for user {user.username}: Status code {response.status_code}")
    except requests.RequestException as e:
        print(f"ERROR: Error activating kill switch for user {user.username}: {e}")


# QUICK EXIT WHILE CLOSING STOPLOSS TESTED OK--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------


# OPTIMIZED CODE FOR QUICK EXIT PERFOMANCE IS Execution Time: 0.55 seconds -----------------------------------------------------------------------------------------------------------------------------------------------------------------


import time
def autoclosePositionProcess():
    start_time = time.time()  # Start time tracking
    print("AUTO CLOSE POSITIONS PROCESS RUNNING....")
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)
    print(f"Current date and time: {now.strftime('%Y-%m-%d %H:%M:%S')}")

    # Execute only during trading hours (Monday to Friday, 9 AM to 4 PM)
    if now.weekday() < 5 and (9 <= now.hour < 16):
        try:
            print("STARTING AUTO CLOSE POSITION MONITORING PROCESS...!")
            # Fetch only active users with quick_exit enabled
            active_users = User.objects.filter(is_active=True, status=True, quick_exit=True).select_related()

            if not active_users.exists():
                print("No User Found.(May be Killed Already/Not Active)")
                print("Auto Quick Exit process completed successfully.")
                elapsed_time = time.time() - start_time
                print(f"Execution Time: {elapsed_time:.2f} seconds")
                return JsonResponse({'status': 'success', 'message': 'Monitoring process completed'})

            for user in active_users:
                try:
                    dhan_client_id = user.dhan_client_id
                    dhan_access_token = user.dhan_access_token
                    print(f"STARTING QUICK CLOSE POSITION : Processing user: {user.username}, Client ID: {dhan_client_id}")
                    
                    # Fetch control data (single query)
                    control_data = Control.objects.filter(user=user).first()
                    dhan = dhanhq(dhan_client_id, dhan_access_token)
                    order_list = dhan.get_order_list()
                    traded_order_count = get_traded_order_count(order_list)
                    if traded_order_count > 0:
                        latest_entry = order_list['data'][0]
                        if (latest_entry['orderType'] == 'STOP_LOSS' and 
                            latest_entry['orderStatus'] == 'CANCELLED' and 
                            latest_entry['transactionType'] == 'SELL'):
                            
                            sl_order_id = latest_entry['orderId']
                            symbol = latest_entry['tradingSymbol']
                            security_id = latest_entry['securityId']
                            client_id = latest_entry['dhanClientId']
                            exchange_segment = latest_entry['exchangeSegment']
                            quantity = latest_entry['quantity']
                            traded_price = float(latest_entry['price'])
                            
                            print("***************************************************************************")
                            print("LATEST CANCELLED STOPLOSS ENTRY DETECTED          : True")
                            print("QUICK EXIT : SELL ORDER PAYLOAD DATA FOR USER     :", user.username)
                            print("SECURITY ID                                       :", security_id)
                            print("CLIENT ID                                         :", client_id)
                            print("EXCHANGE SEGMENT                                  :", exchange_segment)
                            print("QUANTITY                                          :", quantity)
                            print("TRADE PRICE                                       :", traded_price)
                            print("***************************************************************************")
                            
                            # Attempt to place a sell order
                            try:
                                sellOrderResponse = dhan.place_order(
                                    security_id=security_id, 
                                    exchange_segment=exchange_segment,
                                    transaction_type='SELL',
                                    quantity=quantity,
                                    order_type='MARKET',
                                    product_type='INTRADAY',
                                    price=0
                                )
                                
                                print("Sell Order Response:", sellOrderResponse)
                                
                                # Log the sell order response in the database with a single transaction
                                with transaction.atomic():
                                    DhanKillProcessLog.objects.create(user=user, log=sellOrderResponse, order_count=quantity)
                                    
                                    # Check for failure in the sell order response
                                    if sellOrderResponse.get('status') == 'failure':
                                        error_message = sellOrderResponse.get('remarks', {}).get('error_message', 'Unknown error')
                                        error_code = sellOrderResponse.get('remarks', {}).get('error_code', 'Unknown code')
                                        
                                        # Log the failure message in the database
                                        DhanKillProcessLog.objects.create(
                                            user=user,
                                            log={"error_message": error_message, "error_code": error_code},
                                            order_count=0
                                        )
                                        
                                        print("Order failed:", error_message)
                                
                                print(f"INFO: Position Closing Executed Successfully..!")
                            
                            except Exception as e:
                                # Log any exceptions that occur during the sell order process
                                DhanKillProcessLog.objects.create(
                                    user=user,
                                    log={"error_message": str(e), "error_code": "Exception"},
                                    order_count=0
                                )
                                print("An error occurred while executing the sell order:", str(e))

                        else:
                            print(f"INFO: No Open Order for User {user.username}")

                    else:
                        print(f"INFO: No Open Order for User :{user.username}")

                except Exception as e:
                    print(f"ERROR: Error processing user {user.username}: {e}")

            print("Auto Quick Exit process completed successfully.")
            elapsed_time = time.time() - start_time
            print(f"Execution Time: {elapsed_time:.2f} seconds")
            return JsonResponse({'status': 'success', 'message': 'Monitoring process completed'})

        except Exception as e:
            print(f"ERROR: Error in stoploss monitoring process: {e}")
            elapsed_time = time.time() - start_time
            print(f"Execution Time: {elapsed_time:.2f} seconds")
            return JsonResponse({'status': 'error', 'message': 'An error occurred'}, status=500)

    else:
        print("INFO: Current time is outside of the scheduled range.")
        elapsed_time = time.time() - start_time
        print(f"Execution Time: {elapsed_time:.2f} seconds")


def get_traded_order_count(order_list):
    # Check if 'data' key is in order_list and that 'data' is a list
    if 'data' not in order_list or not isinstance(order_list['data'], list) or not order_list['data']:
        return 0
    
    # Calculate traded_count if data list is not empty
    traded_count = len([order for order in order_list['data'] if order.get('orderStatus') == 'TRADED'])
    return traded_count if traded_count else 0

def get_order_count(order_list):
    # Check if 'data' key is in order_list and that 'data' is a list
    if 'data' not in order_list or not isinstance(order_list['data'], list) or not order_list['data']:
        return 0
    
    # Calculate traded_count without filtering by order status
    traded_count = len(order_list['data'])  # Count all orders in the data list
    return traded_count if traded_count else 0


# AUTO STOPLOSS PROCESS : TESTED OK  ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

def autoStopLossLotControlProcess():
    print("Auto Stop Loss Process Running")
    ist = pytz.timezone('Asia/Kolkata')
    now =  datetime.now(ist)
    print(f"Current date and time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    if now.weekday() < 5 and (9 <= now.hour < 16):  # Monday to Friday, 9 AM to 4 PM
        try:
            active_users = User.objects.filter(is_active=True,  status=True, auto_stop_loss=True)
            print("STARTING AUTO STOP LOSS MONITORING PROCESS......................!")
            for user in active_users:
                try:
                    if  user.auto_stop_loss:
                        dhan_client_id = user.dhan_client_id
                        dhan_access_token = user.dhan_access_token
                        print(f"AUTO STOP LOSS MONITORING PROCESS : Processing user: {user.username}, Client ID: {dhan_client_id}")
                        # Fetch control data
                        control_data = Control.objects.filter(user=user).first()
                        stoploss_parameter = float(control_data.stoploss_parameter)
                        max_lot_size_limit = control_data.max_lot_size_limit
                        
                        # Initialize Dhan client
                        dhan = dhanhq(dhan_client_id, dhan_access_token)
                        order_list = dhan.get_order_list()
                        # Step 1: Sort filtered orders by timestamp in descending order
                        if not order_list['data'] == []:
                            latest_entry = order_list['data'][0]
                            if latest_entry['transactionType'] == 'BUY' and latest_entry['orderStatus'] == 'TRADED':
                                security_id = latest_entry['securityId']
                                traded_symbol = latest_entry['tradingSymbol']
                                client_id = latest_entry['dhanClientId']
                                exchange_segment = latest_entry['exchangeSegment']
                                quantity = latest_entry['quantity']
                                traded_price = float(latest_entry['price'])
                                traded_quantity = quantity
                                lot_control_check = lot_control_process(traded_quantity, traded_symbol, max_lot_size_limit )
                                pending_sl_orders = get_pending_order_filter_dhan(order_list)
                                if not lot_control_check:
                                    sell_qty = quantity - max_lot_size_limit
                                    stoploss_response = dhan.place_order(
                                            security_id=security_id, 
                                            exchange_segment=exchange_segment,
                                            transaction_type='SELL',
                                            quantity=sell_qty,
                                            order_type='MARKET',
                                            product_type='INTRADAY',
                                            price=0)
                                    lot_control_check = True
                                    quantity = max_lot_size_limit

                                sl_price, sl_trigger = calculateslprice(traded_price, stoploss_parameter, control_data.stoploss_type, traded_symbol, quantity )
                                print("traded_quantitytraded_quantity", traded_quantity)
                                print("***************************************************************************")
                                print("LOT CHECK                                          :", lot_control_check)
                                print("MAX LOT                                            :", max_lot_size_limit)
                                print("SYMBOL                                             :", traded_symbol)
                                print("AUTO STOP LOSS PROCESS FOR USER                    :" ,user.username )
                                print("TRADE PRICE                                        :", traded_price)
                                print("PRICE                                              :", sl_price)
                                print("TRIGGER PRICE                                      :", sl_trigger)
                                print(f"SECURITY ID                                       : {security_id}")
                                print(f"CLIENT ID                                         : {client_id}")
                                print(f"EXCHANGE SEGMENT                                  : {exchange_segment}")
                                print(f"QUANTITY                                          : {quantity}")
                                print("***************************************************************************")
                                try:
                                    if pending_sl_orders and lot_control_check:
                                        print(f"INFO: MODIFYING EXISTING STOP LOSS ORDER FOR : {user.username}")
                                        for order in pending_sl_orders:
                                            exst_qty = int(order['quantity'])
                                            addon_qty = int(quantity)
                                            total_qty = exst_qty + addon_qty
                                            modify_slorder_response = dhan.modify_order(
                                                order_id=order['orderId'],
                                                quantity=total_qty,
                                                order_type=order['orderType'],
                                                leg_name=order['legName'],
                                                price=order['price'],
                                                trigger_price=order['triggerPrice'],
                                                validity=order['validity'],
                                                disclosed_quantity=order['disclosedQuantity']
                                            )

                                            # Log the response after modifying stop loss order
                                            DhanKillProcessLog.objects.create(
                                                user=user,
                                                log=modify_slorder_response,
                                                order_count=total_qty
                                            )

                                            print("Stop Loss Modified Response:", modify_slorder_response)
                                            print("INFO: Stop Loss Order Modified Successfully..!")
                                    
                                    elif lot_control_check:
                                        # Place a new stop loss order if no existing orders
                                        print(f"INFO: EXECUTING NEW STOP LOSS ORDER FOR : {user.username}")
                                        stoploss_response = dhan.place_order(
                                            security_id=security_id,
                                            exchange_segment=exchange_segment,
                                            transaction_type='SELL',
                                            quantity=quantity,
                                            order_type='STOP_LOSS',
                                            product_type='INTRADAY',
                                            price=sl_price,
                                            trigger_price=sl_trigger
                                        )

                                        # Log the response after placing stop loss order
                                        DhanKillProcessLog.objects.create(
                                            user=user,
                                            log=stoploss_response,
                                            order_count=quantity
                                        )

                                        # Check for failure in response and save the error message if present
                                        if stoploss_response.get('status') == 'failure':
                                            error_message = stoploss_response.get('remarks', {}).get('error_message', 'Unknown error')
                                            error_code = stoploss_response.get('remarks', {}).get('error_code', 'Unknown code')
                                            DhanKillProcessLog.objects.create(
                                                user=user,
                                                log={"error_message": error_message, "error_code": error_code},
                                                order_count=0
                                            )
                                            print("Stop Loss Order failed:", error_message)
                                        
                                        print("INFO: STOPLOSS ORDER RESPONSE:", stoploss_response)
                                    
                                    else:
                                        print(f"INFO: LOT CONTROL CHECK FAILED..! FOR : {user.username}")

                                except Exception as e:
                                    # Log any exceptions that occur during the stop loss order process
                                    DhanKillProcessLog.objects.create(
                                        user=user,
                                        log={"error_message": str(e), "error_code": "Exception"},
                                        order_count=0
                                    )
                                    print("An error occurred while processing the stop loss order:", str(e))
                            else:
                                print(f"INFO: No Recent BUY  Order found for User {user.username}")

                        else:
                            print(f"INFO: No Recent Order found for User {user.username}")
                        
                    else:
                        print(f"WARNING: Auto SL Disabled for User : {user.username}")

                except Exception as e:
                    print(f"ERROR: Error processing user {user.username}: {e}")

            print(f"INFO :No User Found.(May be Killed Already/Not Active)")
            print(f"INFO : Auto Stoplos sMonitoring process completed successfully.")
            return JsonResponse({'status': 'success', 'message': 'Monitoring process completed'})

        except Exception as e:
            print(f"ERROR: Error in  stoploss monitoring process: {e}")
            return JsonResponse({'status': 'error', 'message': 'An error occurred'}, status=500)
    else:
        print("INFO: Current time is outside of the scheduled range.")


def lot_control_process(traded_quantity, traded_symbol, max_lot_size_limit):
    # Map prefixes to default lot counts
    lot_count_map = {
        "FINNIFTY": 25,
        "NIFTYBANK": 15,
        "MIDCP": 50
    }
    
    # Get the default lot count based on the symbol prefix, default to 25 if no match
    default_lot_count = next((count for prefix, count in lot_count_map.items() if traded_symbol.startswith(prefix)), 75)
    
    # Calculate the actual lot count
    actual_lot_count = traded_quantity / default_lot_count
    
    # Check if the lot size is within the limit
    return max_lot_size_limit >= actual_lot_count

def get_default_lot_count(traded_symbol):
    # Map prefixes to default lot counts
    lot_count_map = {
        "FINNIFTY": 25,
        "NIFTYBANK": 15,
        "MIDCP": 50
    }
    
    # Get the default lot count based on the symbol prefix, default to 25 if no match
    return next((count for prefix, count in lot_count_map.items() if traded_symbol.startswith(prefix)), 75)


def calculateslprice(traded_price, stoploss_parameter, stoploss_type, traded_symbol, quantity):
    # Check the value of stoploss_type
    if stoploss_type == 'percentage':
        # Calculate stop-loss price as a percentage of traded_price
        sl_price = traded_price * (1 - stoploss_parameter / 100)
    elif stoploss_type == 'points':
        # Calculate stop-loss price by directly subtracting points from traded_price
        sl_price = traded_price - stoploss_parameter
    elif stoploss_type == "price":
        actual_stoploss_parameter =  stoploss_parameter // quantity 
        sl_price = traded_price - actual_stoploss_parameter

    # Calculate slippage and trigger level for both types
    slippage = float(settings.TRIGGER_SLIPPAGE)
    sl_price = round(sl_price / slippage) * slippage
    sl_trigger = sl_price + slippage * 20
    sl_price = round(sl_price, 2)
    sl_trigger = round(sl_trigger, 2)
    
    return sl_price, sl_trigger


def get_pending_order_filter_dhan(response): 
    # Check if the response contains 'data'
    if 'data' not in response:
        return 0
    pending_sl_orders = [
        order for order in response['data']
        if order.get('orderStatus') == 'PENDING' and order.get('transactionType') == 'SELL'
    ]
    if not pending_sl_orders:
        return False  
    return pending_sl_orders

# ACCOUNT OVERVIEW LOGGING :  TESTED OK --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

def check_and_update_daily_account_overview():
    print("INFO: ACCOUNT OVERVIEW PROCESS RUNNING ....!")

    # Set timezone and flags for opening and closing runs
    ist = pytz.timezone('Asia/Kolkata')
    current_time = datetime.now(ist)
    today = current_time.date()
    current_hour = current_time.hour
    is_first_run = current_hour == 9
    is_last_run = current_hour == 15
    # Check if the current time is 9:00 AM on a weekday
    is_weekday_9am = (
        current_time.weekday() < 5 and  # Monday to Friday (0-4)
        current_time.hour == 9 and
        current_time.minute == 0
    )


    # Query active users
    active_users = User.objects.filter(is_active=True)
    for user in active_users:
        try:
            dhan_client_id = user.dhan_client_id
            dhan_access_token = user.dhan_access_token

            # Initialize the Dhan client
            dhan = dhanhq(dhan_client_id, dhan_access_token)
            
            # Fetch data
            order_list = dhan.get_order_list() or []
            actual_order_count = get_traded_order_count(order_list)

            # Compare with the stored order count in User model
            if user.last_order_count != actual_order_count:
                # Update the User model with the new order count
                user.last_order_count = actual_order_count
                user.save()
                print(f"INFO: Order count changed for {user.username}. Executing update process.")

                # Check specific order conditions for triggering updates
                if actual_order_count and actual_order_count % 2 == 0 or is_weekday_9am:
                    latest_entry = order_list['data'][0]
                    # if ((latest_entry['orderStatus'] == 'TRADED' or latest_entry['orderStatus'] == 'REJECTED') and latest_entry['transactionType'] == 'SELL'): 
                    time.sleep(10)
                    # Fetch funds and positions data
                    fund_data = dhan.get_fund_limits()
                    position_data = dhan.get_positions()

                    # Calculate traded orders and expenses
                    total_expense = actual_order_count * float(settings.BROKERAGE_PARAMETER)
                    total_realized_profit = sum(
                        position.get('realizedProfit', 0) for position in (position_data.get('data', []) if position_data else [])
                    )
                    opening_balance = float(fund_data['data'].get('sodLimit', 0.0)) if fund_data else 0.0
                    closing_balance = float(fund_data['data'].get('availabelBalance', 0.0)) if fund_data else 0.0
                    actual_profit = total_realized_profit - total_expense

                    # Set day_open and day_close fields based on the time of day
                    day_open = is_first_run
                    day_close = is_last_run 

                    day_open = False
                    if is_weekday_9am:
                        day_open = True

                    # Create or update the DailyAccountOverview entry
                    DailyAccountOverview.objects.create(
                        user=user,
                        opening_balance=opening_balance,
                        pnl_status=total_realized_profit,
                        actual_profit=actual_profit,
                        expenses=total_expense,
                        closing_balance=closing_balance,
                        order_count=actual_order_count,
                        day_open=day_open,
                        day_close=day_close
                    )
                    # Get the first matching record (if any)
                    daily_goal_data = DailyGoalReport.objects.filter(user=user, date=today).first()

                    if daily_goal_data:
                        # Assign the actual profit to the progress field (make sure 'actual_profit' is defined)
                        daily_goal_data.progress = actual_profit
                        if daily_goal_data.gained_amount <= actual_profit:
                            daily_goal_data.is_achieved=True
                        # Save the updated record
                        daily_goal_data.save()
                        print(f"INFO: DailyGoalReport updated successfully for {user.username}")
                    else:
                        print(f"INFO:No DailyGoalReport found for the given user and date.")

                    print(f"INFO: DailyAccountOverview updated successfully for {user.username}")
            else:
                print(f"INFO: No change in order count for {user.username}. No update required.")

        except Exception as e:
            print(f"INFO: Error processing user {user.username}: {e}")
            continue


# AUTO ADMIN SWITCHING PROCESS :  TESTED OK ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

# def autoAdminSwitchingProcess():
#     print(f"INFO:  AUTO ADMIN SWITCHING PROCESS : RUNNING")
#     ist = pytz.timezone('Asia/Kolkata')
#     current_hour = datetime.now(ist).hour
#     try:
#         if current_hour == 9:
#             # Set vicky as superuser and remove superuser status from juztin and tradingwitch every day at 9 AM
#             acting_admin = settings.ACTING_ADMIN
#             acting_traders_list = settings.ACTING_TRADERS
#             vicky = User.objects.get(username=acting_admin)
#             vicky.is_superuser = True
#             vicky.save()
#             print(f"INFO: Set", acting_admin, "as superuser at 9 AM")

#             for username in acting_traders_list:
#                 user = User.objects.get(username=username)
#                 user.is_superuser = False
#                 user.save()
#                 print(f"INFO: Removed superuser status from '{username}'")

#         elif current_hour == 16:
#             # Set tradingwitch as superuser and remove superuser status from vicky every day at 4 PM
#             dev_admin = settings.DEV_ADMIN
#             tradingwitch = User.objects.get(username=dev_admin)
#             tradingwitch.is_superuser = True
#             tradingwitch.save()
#             print("INFO: Set", dev_admin, "as superuser at 4 PM")

#             vicky = User.objects.get(username='vicky')
#             vicky.is_superuser = False
#             vicky.save()
#             print("INFO: Removed superuser status from 'vicky'")

#         else:
#             print("Admin Switching Process not in time range")

#     except User.DoesNotExist as e:
#         print(f"ERROR: User not found: {e}")
#     except Exception as e:
#         print(f"ERROR: An error occurred in update_superuser_status: {e}")

# RESTORE SUPER ADMIN :  TESTED OK -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

def restore_super_user_after_market():
    dev_admin = settings.DEV_ADMIN
    user = User.objects.filter(username=dev_admin).first()
    if user:
        user.is_superuser = True
        user.save()
    else:
        print("Developer admin user not found.")


# CRON JOBS STRAT PROCESS :  TESTED OK -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

def update_order_history():
    # Get active users
    active_users = User.objects.filter(is_active=True)

    for user in active_users:
        try:
            # Get Dhan client information
            dhan_client_id = user.dhan_client_id
            dhan_access_token = user.dhan_access_token

            # Initialize the Dhan client
            dhan = dhanhq(dhan_client_id, dhan_access_token)

            # Fetch order list
            order_list = dhan.get_order_list() or []
            actual_order_count = len(order_list.get('data', []))

            # Process if there are orders
            if actual_order_count:
                latest_entry = order_list['data'][0]  # Assuming you want the first entry
                # Fetch fund and position data
                fund_data = dhan.get_fund_limits() or {}
                position_data = dhan.get_positions() or {}

                # Calculate expenses and profits
                total_expense = actual_order_count * float(settings.BROKERAGE_PARAMETER)
                total_realized_profit = sum(
                    position.get('realizedProfit', 0) for position in position_data.get('data', [])
                )

                # Opening and closing balances
                opening_balance = float(fund_data.get('data', {}).get('sodLimit', 0.0))
                closing_balance = float(fund_data.get('data', {}).get('withdrawableBalance', 0.0))

                # Actual profit calculation
                actual_profit = total_realized_profit - total_expense

                # Create or update OrderHistoryLog
                OrderHistoryLog.objects.create(
                    user=user,
                    order_data=order_list,  # Store the full order list or just relevant data
                    date=datetime.today().date(),
                    order_count=actual_order_count,
                    profit_loss=actual_profit,
                    eod_balance=closing_balance,
                    sod_balance=opening_balance,
                    expense=total_expense
                )

                print(f"INFO: OrderHistoryLog updated successfully for {user.username}")

            else:
                print(f"INFO: No orders found for {user.username}. No update required.")

        except Exception as e:
            print(f"INFO: Error processing user {user.username}: {e}")
            continue



# CRON JOBS STRAT PROCESS :  TESTED OK -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------


def start_scheduler():
    scheduler = BackgroundScheduler()
    ist = pytz.timezone('Asia/Kolkata')

    # SELF PING TESTED OK
    scheduler.add_job(self_ping, IntervalTrigger(seconds=180))

    #  RESTORE KILL SWITCH BY 9 AM AND 4 PM TESTED OK
    scheduler.add_job(restore_user_kill_switches, CronTrigger(day_of_week='mon-fri', hour=9, minute=0,  timezone=ist))
    scheduler.add_job(restore_super_user_after_market, CronTrigger(day_of_week='mon-fri', hour=15, minute=30,  timezone=ist))

    #  ORDER COUNT-KILL FEATURE TESTED OK 
    scheduler.add_job(auto_order_count_monitoring_process, IntervalTrigger(seconds=2), max_instances=3, replace_existing=True)

    #  QUICK EXIT FEATURE TESTED OK 
    scheduler.add_job(autoclosePositionProcess, IntervalTrigger(seconds=1), max_instances=3, replace_existing=True)

    #  AUTO STOPLOSS FEATURE TESTED OK
    # scheduler.add_job(autoStopLossLotControlProcess, IntervalTrigger(seconds=1), max_instances=3, replace_existing=True)
    scheduler.add_job(autoStopLossLotControlProcess, IntervalTrigger(seconds=2), max_instances=2, replace_existing=True)

    #  AUTO ADMIN SWITCHING PROCESS TESTED OK NOT USING NOW
    # scheduler.add_job(autoAdminSwitchingProcess, IntervalTrigger(hours=1))

    #  HOURLY DATA LOG MONITORING TESTED OK
    scheduler.add_job( check_and_update_daily_account_overview, IntervalTrigger(seconds=15), max_instances=10, replace_existing=True)

    #  ORDER DATA  LOG MONITORING TESTED OK
    scheduler.add_job( update_order_history, CronTrigger(day_of_week='mon-fri', hour=15, minute=30,  timezone=ist))
    
    


    scheduler.start()
    print("INFO: Scheduler started.")

    # Shut down the scheduler when exiting the app
    atexit.register(lambda: scheduler.shutdown())



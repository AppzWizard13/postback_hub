# import logging
# import requests
# import asyncio

# logger = logging.getLogger(__name__)

# @aiocron.crontab('*/3 * * * * *')
# async def self_ping():
#     try:
#         loop = asyncio.get_event_loop()
#         response = await loop.run_in_executor(None, requests.get, 'your_django_app_endpoint')
#         print(f"Health check response: {response.status_code}")
#     except Exception as e:
#         logger.error(f"Error in self_ping: {e}")
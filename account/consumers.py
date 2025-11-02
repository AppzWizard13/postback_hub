import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import User  # Import your user model
import asyncio
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from dhanhq import orderupdate
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
User = get_user_model()  # Reference your custom user model
import asyncio

class OrderUpdateConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Extract the username from the WebSocket URL
        self.username = self.scope["url_route"]["kwargs"].get("username")

        # Fetch the user's Dhan credentials from the database
        user = await self.get_user_credentials(self.username)
        if user:
            self.dhan_client_id = user.dhan_client_id
            self.dhan_access_token = user.dhan_access_token
            self.order_feed_wss = "wss://api-order-update.dhan.co"
            await self.accept()
            asyncio.create_task(self.run_order_update())
        else:
            await self.close()  # Close the connection if the user is not found

    async def run_order_update(self):
        # Create an order socket with user credentials
        order_client = orderupdate.OrderSocket(self.dhan_client_id, self.dhan_access_token)
        
        while True:
            try:
                order_client.connect_to_dhan_websocket_sync()
                while True:
                    order_data = await self.get_order_update(order_client)  # Call the method here
                    if order_data:  # Check if data is valid
                        await self.send(text_data=json.dumps(order_data))
                    await asyncio.sleep(1)  # Adjust the delay as necessary
            except Exception as e:
                print(f"Error: {e}")
                await asyncio.sleep(5)

    async def get_order_update(self, order_client):
        # Implement logic to receive messages from the WebSocket
        try:
            # Assuming the order_client has a method to receive messages
            return order_client.receive()  # Adjust according to your API usage
        except Exception as e:
            print(f"Failed to get order update: {e}")
            return None

    async def get_user_credentials(self, username):
        # Fetch the user from the database using the username
        try:
            user = await database_sync_to_async(User.objects.get)(username=username)
            return user
        except User.DoesNotExist:
            return None

    async def disconnect(self, close_code):
        pass  # Handle disconnect if necessary

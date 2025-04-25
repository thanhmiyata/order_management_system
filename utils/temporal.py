from temporalio.client import Client
import asyncio

async def get_temporal_client() -> Client:
    """
    Khởi tạo và trả về Temporal client
    """
    client = await Client.connect("localhost:7233")
    return client 
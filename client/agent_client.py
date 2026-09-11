import asyncio
import httpx

BASE_URL = "http://localhost:8000"


async def main():
    print(f"Connecting to lead-distro event stream at {BASE_URL}/event/stream")
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("GET", f"{BASE_URL}/event/stream") as response:
            print("Connected, waiting for events...")
            # Use aiter_lines() instead of iter_lines() for async streaming
            async for line in response.aiter_lines():
                if line:
                    print(f"[Lead delivery event] {line}")


if __name__ == "__main__":
    asyncio.run(main())
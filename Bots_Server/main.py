import asyncio
import logging
import sys
from servers.http2_server import HTTP2Server

async def run_servers():
    """Start multiple HTTP/2 servers"""
    servers = [
        HTTP2Server("localhost", 8000, "server_1"),
        HTTP2Server("localhost", 8001, "server_2"),
        HTTP2Server("localhost", 8002, "server_3")
    ]
    
    tasks = [asyncio.create_task(server.run()) for server in servers]
    await asyncio.gather(*tasks, return_exceptions=True)

async def run_bots():
    """Run bot simulation"""
    # Import only when needed
    from bots.bot_controller import BotController
    
    controller = BotController()
    controller.create_bots()
    
    # Run continuous simulation for 2 hours
    await controller.run_continuous_simulation(duration=7200)

async def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py [servers|bots|both]")
        return
    
    mode = sys.argv[1]
    
    if mode == "servers":
        await run_servers()
    elif mode == "bots":
        await run_bots()
    elif mode == "both":
        # Run both servers and bots
        server_task = asyncio.create_task(run_servers())
        await asyncio.sleep(5)  # Give servers time to start
        bot_task = asyncio.create_task(run_bots())
        
        await asyncio.gather(server_task, bot_task, return_exceptions=True)
    else:
        print("Invalid mode. Use 'servers', 'bots', or 'both'")

if __name__ == "__main__":
    asyncio.run(main())

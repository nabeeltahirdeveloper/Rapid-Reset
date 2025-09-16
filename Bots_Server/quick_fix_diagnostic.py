#!/usr/bin/env python3
"""
Quick diagnostic and fix for the enhanced system
"""

import asyncio
import httpx
import time

async def test_server_basic():
    """Test if servers are working at basic level"""
    print("🔍 Testing basic server connectivity...")
    
    servers = ["http://localhost:8000", "http://localhost:8001", "http://localhost:8002"]
    
    for server in servers:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Test basic endpoint
                response = await client.get(f"{server}/")
                print(f"✅ {server}/ - Status: {response.status_code}")
                
                # Test API endpoint
                response = await client.get(f"{server}/api/data")
                print(f"✅ {server}/api/data - Status: {response.status_code}")
                
                # Test enhanced endpoints
                response = await client.get(f"{server}/api/queue-metrics")
                print(f"✅ {server}/api/queue-metrics - Status: {response.status_code}")
                
        except Exception as e:
            print(f"❌ {server} - Error: {e}")
            return False
    
    return True

async def test_heavy_task():
    """Test if heavy computation works"""
    print("🧮 Testing heavy computation endpoint...")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get("http://localhost:8000/heavy-task?n=25")
            print(f"✅ Heavy task - Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Heavy task response: {data}")
            return True
    except Exception as e:
        print(f"❌ Heavy task failed: {e}")
        return False

async def send_test_requests():
    """Send some test requests to see if queue system works"""
    print("📤 Sending test requests...")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Send multiple requests concurrently
            tasks = []
            for i in range(5):
                task = asyncio.create_task(
                    client.get(f"http://localhost:8000/api/data?test={i}")
                )
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            success_count = 0
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    print(f"❌ Request {i} failed: {result}")
                else:
                    print(f"✅ Request {i} - Status: {result.status_code}")
                    success_count += 1
            
            print(f"📊 Success rate: {success_count}/5 ({(success_count/5)*100:.1f}%)")
            return success_count > 0
            
    except Exception as e:
        print(f"❌ Test requests failed: {e}")
        return False

async def main():
    print("=" * 60)
    print("🔧 QUICK DIAGNOSTIC TOOL")
    print("=" * 60)
    
    # Test 1: Basic server connectivity
    if not await test_server_basic():
        print("❌ Basic server test failed!")
        return
    
    # Test 2: Heavy computation
    if not await test_heavy_task():
        print("⚠️ Heavy computation test failed!")
    
    # Test 3: Request processing
    if not await send_test_requests():
        print("❌ Request processing test failed!")
        return
    
    print("\n✅ Basic functionality seems to work!")
    print("💡 The issue might be in the bot configurations...")

if __name__ == "__main__":
    asyncio.run(main())
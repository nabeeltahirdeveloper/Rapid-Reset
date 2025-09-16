# Enhanced HTTP/2 Rapid Reset Attack Analysis System

## 🎯 Overview

This project implements a comprehensive analysis system for studying HTTP/2 Rapid Reset attacks, focusing on how servers handle queue management, client connection tracking, and request abandonment during attack scenarios.

## 🌟 Key Research Questions Addressed

1. **How do servers handle queued requests when clients perform rapid reset attacks?**
2. **What happens to pending requests when attackers disconnect suddenly?**
3. **How long do servers retain client state after disconnection?**
4. **What is the recovery time for normal traffic after rapid reset attacks?**
5. **How do different queue management strategies affect server resilience?**

## 🏗️ Architecture Overview

### Enhanced Queue System
- **Client Connection Tracking**: Monitors individual client lifecycle from connection to disconnection
- **Request Abandonment Detection**: Identifies requests that never receive responses due to client disconnection
- **Reset Timer**: Configurable 2-3 second window to detect if clients reconnect after rapid reset
- **Priority Queue Management**: Separate queues for different request types with intelligent prioritization

### Attack Bot Implementations
1. **Enhanced Rapid Reset Bot**: Multiple attack patterns including burst-and-abandon, sustained flood, and multi-endpoint chaos
2. **Heavy Computation Bot**: Targets CPU-intensive endpoints like Fibonacci calculations
3. **Connection Exhaustion Bot**: Tests connection pool limits and file descriptor exhaustion

### Profiling & Monitoring
- **Real-time Queue Metrics**: Live tracking of queue size, utilization, and abandonment rates
- **Client Connection Analytics**: Connection lifecycle tracking with reconnection detection
- **Attack Pattern Recognition**: Automatic detection of rapid reset patterns and server stress indicators

## 📁 Project Structure

```
├── utils/
│   ├── client_connection_manager.py    # Client lifecycle tracking
│   ├── enhanced_request_queue.py       # Priority queue with abandonment detection
│   └── enhanced_profiling.py           # Attack analysis and profiling
├── servers/
│   ├── http2_server.py                 # Enhanced HTTP/2 server with queue integration
│   ├── templates/dashboard.html        # Real-time monitoring dashboard
│   └── static/dashboard.js             # Interactive dashboard frontend
├── bots/
│   ├── attack_bots/
│   │   ├── enhanced_rapid_reset_bot.py # Advanced rapid reset implementations
│   │   ├── heavy_computation_bot.py    # CPU-intensive attack patterns
│   │   └── connection_exhaustion_bot.py # Connection pool exhaustion
│   └── bot_controller.py               # Orchestrates attack scenarios
├── test_enhanced_system.py             # Comprehensive validation suite
└── main.py                            # System launcher
```

## 🚀 Key Features

### 1. Enhanced Queue Management
- **Client-aware queuing**: Each request is associated with a client connection state
- **Abandonment tracking**: Monitors requests that become "orphaned" when clients disconnect
- **Priority-based processing**: Critical requests (metrics, dashboard) get higher priority
- **Real-time metrics**: Live monitoring of queue state and performance

### 2. Client Connection Lifecycle Management
```python
# Connection states tracked:
- CONNECTED: Active client connection
- DISCONNECTED: Client disconnected, reset timer active
- RECONNECTING: Client attempting to reconnect
- ABANDONED: Client never returned after reset timer
```

### 3. Request Abandonment Detection
- **Reset Timer**: 2-3 second configurable window to detect client returns
- **Abandonment Analysis**: Tracks patterns of request abandonment during attacks
- **Recovery Metrics**: Measures how quickly servers process abandoned requests

### 4. Attack Pattern Implementations

#### Rapid Reset Patterns
- **BURST_AND_ABANDON**: High-intensity bursts followed by immediate disconnection
- **SUSTAINED_FLOOD**: Continuous high-rate requests with random abandonments
- **MULTI_ENDPOINT_CHAOS**: Targets multiple endpoints simultaneously
- **INTERMITTENT_SPIKES**: Alternates between attack and quiet periods

#### Heavy Computation Attacks
- **Fibonacci Overload**: Targets CPU-intensive calculations
- **Mixed Computation**: Combines multiple heavy operations
- **Abandonment During Processing**: Tests server behavior when expensive operations are interrupted

#### Connection Exhaustion
- **Connection Pool Exhaustion**: Overwhelms server connection limits
- **Rapid Open/Close**: High-frequency connection cycling
- **Keep-Alive Abuse**: Holds connections open beyond normal timeouts

## 🔧 Installation & Setup

### Prerequisites
```bash
pip install -r requirements.txt
```

### Required Dependencies
```
asyncio
hypercorn
quart
httpx
h2
psutil
pyyaml
aiohttp
```

### Setup
1. **Create log directories**:
   ```bash
   mkdir -p logs/{server_logs,attack_logs,bot_logs,phase_profiles}
   ```

2. **Configure bot settings** in `config/bot_configs.yaml`

3. **Start servers**:
   ```bash
   python main.py servers
   ```

4. **Run attack scenarios**:
   ```bash
   python main.py bots
   ```

## 📊 Dashboard & Monitoring

### Access Dashboard
- Server 1: http://localhost:8000/dashboard
- Server 2: http://localhost:8001/dashboard  
- Server 3: http://localhost:8002/dashboard

### Key Dashboard Sections

1. **🚨 Attack Detection**
   - Real-time attack pattern recognition
   - Phase indicators (Normal/Attack/Recovery)
   - Queue utilization and abandonment rates

2. **📊 Queue State Analysis**
   - Total queue size over time
   - Active vs. abandoned requests
   - Queue utilization percentage

3. **🔗 Client Connection Lifecycle**
   - Active connections tracking
   - Disconnected and abandoned clients
   - Reconnection patterns

4. **🎯 Attack Pattern Detection**
   - Request rate monitoring
   - Queue overflow risk assessment
   - Attack pattern identification

## 🧪 Testing & Validation

### Comprehensive Test Suite
```bash
python test_enhanced_system.py
```

### Test Scenarios Covered
1. **Server Health Check**: Validates all enhanced endpoints
2. **Queue Metrics Validation**: Tests enhanced queue metrics API
3. **Client Connection Tracking**: Verifies connection lifecycle monitoring
4. **Profiling System**: Tests attack phase profiling
5. **Rapid Reset Attack**: Validates burst-and-abandon patterns
6. **Heavy Computation Attack**: Tests CPU-intensive attack handling
7. **Connection Exhaustion**: Validates connection pool stress testing
8. **Mixed Attack Scenario**: Tests complex multi-bot scenarios

### Expected Test Results
- ✅ All enhanced endpoints respond correctly
- ✅ Queue metrics include abandonment tracking
- ✅ Client connections are properly monitored
- ✅ Attack patterns generate expected abandonment rates
- ✅ Server maintains queue stability under attack
- ✅ Recovery metrics show post-attack normalization

## 📈 Research Insights

### Queue Behavior During Attacks
The system provides detailed insights into:
- **Request Abandonment Patterns**: How different attack patterns affect request completion
- **Queue Recovery Time**: Speed of server recovery after attack cessation  
- **Client Reconnection Behavior**: Patterns of client returns after rapid reset
- **Server Resilience Metrics**: Queue stability and performance under stress

### Key Metrics Collected
1. **Abandonment Rate**: Percentage of requests never completed due to client disconnection
2. **Queue Utilization**: Real-time queue capacity usage during attacks
3. **Client Lifecycle Duration**: Time from connection to abandonment
4. **Recovery Metrics**: Server performance normalization time post-attack
5. **Attack Pattern Recognition**: Automatic classification of attack types

## 🔍 API Endpoints

### Enhanced Monitoring APIs
- `GET /api/queue-metrics`: Detailed queue state and abandonment metrics
- `GET /api/client-connections`: Client connection lifecycle data
- `POST /api/profiling/start/<phase>`: Start attack phase profiling
- `POST /api/profiling/stop/<phase>`: Stop profiling and generate reports
- `GET /metrics`: Comprehensive system and enhanced queue metrics

### Sample API Response (Queue Metrics)
```json
{
  "status": "success",
  "queue_metrics": {
    "queue": {
      "total_size": 45,
      "utilization_percent": 67.2,
      "by_priority": {
        "CRITICAL": 2,
        "HIGH": 12,
        "NORMAL": 28,
        "LOW": 3
      }
    },
    "metrics": {
      "total_abandoned": 156,
      "abandonment_rate": 23.4,
      "active_requests": 45,
      "avg_processing_time_ms": 125.6
    },
    "clients": {
      "active_clients": 8,
      "disconnected_clients": 12,
      "abandoned_clients": 25,
      "total_reconnections": 3
    }
  }
}
```

## 🛠️ Configuration

### Queue Configuration
```yaml
# config/bot_configs.yaml
enhanced_queue:
  maxsize: 1000
  workers: 4
  reset_timeout: 3.0  # Reset timer duration
  cleanup_interval: 5.0
```

### Attack Bot Configuration
```yaml
attack_bots:
  rapid_reset:
    intensities: ["low", "medium", "high"]
    count_per_intensity: 2
  heavy_computation:
    complexities: ["medium", "high", "extreme"]
    fibonacci_range: [25, 40]
  connection_exhaustion:
    strategies: ["connection_pool", "rapid_open_close", "keep_alive_abuse"]
```

## 📚 Usage Examples

### Running Specific Attack Scenarios
```python
from bots.attack_bots.enhanced_rapid_reset_bot import EnhancedRapidResetBot, AttackPattern

# Create burst-and-abandon attack
bot = EnhancedRapidResetBot(
    bot_id="research_attack_001",
    target_servers=["http://localhost:8000"],
    attack_pattern=AttackPattern.BURST_AND_ABANDON,
    intensity="high"
)

# Run for 60 seconds
await bot.run(duration=60)
```

### Monitoring Queue State
```python
import aiohttp

async with aiohttp.ClientSession() as session:
    async with session.get('http://localhost:8000/api/queue-metrics') as response:
        metrics = await response.json()
        print(f"Queue utilization: {metrics['queue_metrics']['queue']['utilization_percent']}%")
        print(f"Abandonment rate: {metrics['queue_metrics']['metrics']['abandonment_rate']}%")
```

### Starting Attack Profiling
```python
# Start profiling for attack phase
async with aiohttp.ClientSession() as session:
    await session.post('http://localhost:8000/api/profiling/start/attack', 
                      json={"scenario": "rapid_reset_analysis"})
```

## 🎯 Research Applications

This system is designed for:
- **HTTP/2 Security Research**: Understanding rapid reset attack impacts
- **Queue Management Studies**: Analyzing server queue behavior under stress
- **Client Connection Analysis**: Studying connection lifecycle during attacks
- **Server Resilience Testing**: Measuring recovery capabilities
- **Attack Pattern Classification**: Identifying and categorizing attack signatures

## 📊 Generated Reports

The system generates detailed reports including:
- **Attack Analysis Reports**: Comprehensive attack pattern analysis
- **Queue Performance Reports**: Detailed queue behavior during attacks
- **Client Connection Reports**: Connection lifecycle and abandonment patterns
- **Server Recovery Reports**: Post-attack recovery metrics and timelines

## 🔬 Future Enhancements

Potential areas for extension:
- Machine learning-based attack pattern recognition
- Adaptive queue management strategies
- Real-time attack mitigation recommendations
- Integration with network-level monitoring
- Advanced visualization and alerting systems

---

**For detailed implementation questions or research collaboration, please refer to the comprehensive test suite and profiling reports generated by the system.**
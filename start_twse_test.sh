#!/bin/bash
# Start both backend and frontend for TWSE testing

set -e

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  🇹🇼 TradingAgents-CN - TWSE Testing Mode                   ║"
echo "╔══════════════════════════════════════════════════════════════╗"
echo ""

# Check MongoDB
echo "📊 Checking MongoDB..."
if ! docker ps | grep -q tradingagents-mongodb; then
    echo "⚠️  MongoDB not running, starting..."
    docker start tradingagents-mongodb || docker-compose up -d mongodb
    sleep 5
fi
echo "✅ MongoDB is running"

# Check Redis
echo "💾 Checking Redis..."
if ! redis-cli ping > /dev/null 2>&1; then
    echo "❌ Redis not running. Start with: sudo systemctl start redis"
    exit 1
fi
echo "✅ Redis is running"

# Check and kill ALL uvicorn processes on port 8000
echo "🔍 Checking for existing backend processes..."
EXISTING_PIDS=$(ps aux | grep "uvicorn app.main:app.*:8000" | grep -v grep | awk '{print $2}')
if [ ! -z "$EXISTING_PIDS" ]; then
    echo "⚠️  Found existing backend processes, killing them..."
    echo "$EXISTING_PIDS" | xargs kill -9 2>/dev/null || true
    sleep 3
    echo "✅ Old backend processes killed"
else
    echo "✅ No existing backend processes found"
fi

# Double-check port is truly free
PORT_PID=$(lsof -ti:8000 2>/dev/null || true)
if [ ! -z "$PORT_PID" ]; then
    echo "⚠️  Port 8000 still in use (PID: $PORT_PID), force killing..."
    kill -9 $PORT_PID 2>/dev/null || true
    sleep 2
fi
echo "✅ Port 8000 is now available"

# Check and kill port 5173 (Vite default)
echo "🔍 Checking port 5173..."
PORT_PID=$(lsof -ti:5173 2>/dev/null || true)
if [ ! -z "$PORT_PID" ]; then
    echo "⚠️  Port 5173 in use (PID: $PORT_PID), freeing..."
    kill $PORT_PID 2>/dev/null || true
    sleep 2
fi
echo "✅ Port 5173 is available"

# Check virtual environment
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found"
    exit 1
fi

# Install frontend dependencies if needed
echo "📦 Checking frontend dependencies..."
if [ ! -d "frontend/node_modules" ]; then
    echo "⚠️  Installing frontend dependencies (this may take a few minutes)..."
    cd frontend
    npm install --silent
    cd ..
    echo "✅ Frontend dependencies installed"
else
    echo "✅ Frontend dependencies already installed"
fi

# Verify TWSE configuration
echo "🇹🇼 Verifying TWSE configuration..."
if grep -q "TWSE_UNIFIED_ENABLED=true" .env; then
    echo "✅ TWSE is enabled"
else
    echo "⚠️  TWSE not enabled in .env"
fi

# Show disabled data sources
echo "📊 Data source configuration:"
grep -E "(TUSHARE|AKSHARE|BAOSTOCK|TWSE)_UNIFIED_ENABLED" .env | while read line; do
    if [[ $line == *"true"* ]]; then
        echo "   ✅ $line"
    else
        echo "   ❌ $line"
    fi
done

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Starting Services...                                        ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Start backend in background
echo "🚀 Starting Backend API (port 8000)..."
source venv/bin/activate
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > logs/backend.log 2>&1 &
BACKEND_PID=$!
echo "   Backend PID: $BACKEND_PID"
echo "   Logs: logs/backend.log"

# Wait for backend to start
echo "⏳ Waiting for backend to start..."
for i in {1..30}; do
    if curl -s http://localhost:8000/ > /dev/null 2>&1; then
        echo "✅ Backend is ready!"
        break
    fi
    sleep 1
    if [ $i -eq 30 ]; then
        echo "❌ Backend failed to start. Check logs/backend.log"
        echo ""
        echo "Last 30 lines of backend.log:"
        tail -30 logs/backend.log
        kill $BACKEND_PID 2>/dev/null || true
        exit 1
    fi
done

# Start frontend in background
echo "🎨 Starting Frontend (port 5173)..."
cd frontend
nohup npm run dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..
echo "   Frontend PID: $FRONTEND_PID"
echo "   Logs: logs/frontend.log"

# Wait for frontend to start
echo "⏳ Waiting for frontend to start..."
for i in {1..30}; do
    if curl -s http://localhost:5173 > /dev/null 2>&1; then
        echo "✅ Frontend is ready!"
        break
    fi
    sleep 1
    if [ $i -eq 30 ]; then
        echo "⚠️  Frontend may still be starting. Check logs/frontend.log"
    fi
done

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  ✅ Services Started Successfully!                           ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "🌐 Access Points:"
echo "   • Frontend:      http://localhost:5173"
echo "   • Backend API:   http://localhost:8000"
echo "   • API Docs:      http://localhost:8000/docs"
echo ""
echo "📊 TWSE Testing Mode:"
echo "   • Chinese markets: DISABLED"
echo "   • Taiwan stocks:   ENABLED"
echo "   • Popular stocks:  2330.TW (TSMC), 2317.TW (Foxconn)"
echo ""
echo "📋 Process IDs:"
echo "   • Backend:  $BACKEND_PID"
echo "   • Frontend: $FRONTEND_PID"
echo ""
echo "📝 Logs:"
echo "   • Backend:  tail -f logs/backend.log"
echo "   • Frontend: tail -f logs/frontend.log"
echo ""
echo "⏹️  To stop services:"
echo "   kill $BACKEND_PID $FRONTEND_PID"
echo ""
echo "Press Ctrl+C to view logs (services will keep running in background)"
echo ""

# Follow logs
tail -f logs/backend.log logs/frontend.log

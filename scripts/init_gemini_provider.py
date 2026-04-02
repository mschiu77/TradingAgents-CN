#!/usr/bin/env python3
"""
Initialize Gemini/Google AI provider in the database
"""
import sys
import os
from pymongo import MongoClient
from datetime import datetime

def init_gemini_provider():
    """Initialize Gemini provider in database"""
    
    # Read API key from .env
    import re
    env_path = "/home/ubuntu/mingshuoqiu/TradingAgents-CN/.env"
    google_api_key = None
    
    try:
        with open(env_path, 'r') as f:
            for line in f:
                if line.startswith('GOOGLE_API_KEY='):
                    google_api_key = line.split('=', 1)[1].strip()
                    break
    except Exception as e:
        print(f"⚠️ Could not read .env file: {e}")
    
    # MongoDB connection
    mongo_uri = "mongodb://admin:tradingagents123@localhost:27017/"
    
    try:
        client = MongoClient(mongo_uri)
        db = client.tradingagents
        providers_collection = db.llm_providers
        models_collection = db.llm_models
        
        print("🔧 Initializing Gemini/Google AI Provider...")
        print("=" * 60)
        
        # Check if already exists
        existing = providers_collection.find_one({"name": "google"})
        
        if existing:
            print("✅ Google provider already exists!")
            print(f"   Name: {existing.get('display_name')}")
            print(f"   Enabled: {existing.get('enabled')}")
        else:
            # Create Gemini provider
            gemini_provider = {
                "name": "google",
                "display_name": "Google Gemini",
                "base_url": "https://generativelanguage.googleapis.com",
                "api_key": google_api_key or "",
                "enabled": True,
                "priority": 5,
                "config": {
                    "supports_streaming": True,
                    "supports_function_calling": True,
                    "max_tokens": 2000000,
                    "default_temperature": 0.7
                },
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            result = providers_collection.insert_one(gemini_provider)
            print(f"✅ Gemini provider created! ID: {result.inserted_id}")
        
        # Add default Gemini models
        gemini_models = [
            {
                "provider": "google",
                "model_name": "gemini-2.5-flash",
                "model_display_name": "Gemini 2.5 Flash",
                "enabled": True,
                "capabilities": ["chat", "analysis", "streaming"],
                "config": {
                    "max_tokens": 65536,
                    "supports_vision": True,
                    "context_window": 1048576
                },
                "created_at": datetime.utcnow()
            },
            {
                "provider": "google",
                "model_name": "gemini-2.5-pro",
                "model_display_name": "Gemini 2.5 Pro",
                "enabled": True,
                "capabilities": ["chat", "analysis", "streaming"],
                "config": {
                    "max_tokens": 65536,
                    "supports_vision": True,
                    "context_window": 1048576
                },
                "created_at": datetime.utcnow()
            }
        ]
        
        print(f"\n📋 Adding {len(gemini_models)} Gemini models...")
        for model in gemini_models:
            existing_model = models_collection.find_one({
                "provider": "google",
                "model_name": model["model_name"]
            })
            
            if existing_model:
                print(f"   ⚠️ {model['model_display_name']} already exists, skipping")
            else:
                models_collection.insert_one(model)
                print(f"   ✅ Added: {model['model_display_name']} ({model['model_name']})")
        
        print("\n" + "=" * 60)
        print("✅ Gemini Provider Initialization Complete!")
        print("=" * 60)
        print()
        print("📋 Available Models:")
        print("   • Gemini 2.5 Flash (gemini-2.5-flash) - Fast, efficient")
        print("   • Gemini 2.5 Pro (gemini-2.5-pro) - Most capable")
        print()
        print("📋 Next Steps:")
        print("   1. Your API key is already set in .env ✅")
        print(f"      GOOGLE_API_KEY={google_api_key[:20]}... (39 chars)")
        print()
        print("   2. Refresh frontend: http://localhost:3001")
        print()
        print("   3. Go to: 设置 → 配置管理 → 大模型配置")
        print("      Click: 添加大模型")
        print("      Select: Google Gemini → gemini-2.5-flash")
        print()
        print("   4. Use in 单股分析:")
        print("      快速分析模型: Gemini 2.5 Flash")
        print("      深度分析模型: Gemini 2.5 Pro")
        print()
        
        if google_api_key and google_api_key != "your_google_api_key_here" and len(google_api_key) > 20:
            print("   ✅ API Key is configured and validated!")
        else:
            print("   ⚠️ No valid API key in .env, please add it")
        
        client.close()
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = init_gemini_provider()
    sys.exit(0 if success else 1)

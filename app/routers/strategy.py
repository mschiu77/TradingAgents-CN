"""
策略研究路由
支持用户创建、管理和回测交易策略
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import logging

from app.core.database import get_mongo_db
from app.routers.auth_db import get_current_user
from app.core.response import ok, fail

logger = logging.getLogger(__name__)
router = APIRouter()


# ==================== Models ====================

class StrategyCreateRequest(BaseModel):
    """创建策略请求"""
    name: str = Field(..., description="策略名称")
    market: str = Field(..., description="市场类型: CN/TW/HK/US")
    prompt: str = Field(..., description="策略描述（自然语言）")


class BacktestRequest(BaseModel):
    """回测请求"""
    start_date: str = Field(..., description="开始日期 YYYY-MM-DD")
    end_date: str = Field(..., description="结束日期 YYYY-MM-DD")
    initial_capital: float = Field(default=1000000, description="初始资金")
    commission_rate: float = Field(default=0.0003, description="手续费率")
    slippage: float = Field(default=0.0001, description="滑点")


# ==================== Endpoints ====================

@router.get("/strategies", response_model=dict)
async def get_strategies(current_user: dict = Depends(get_current_user)):
    """获取用户的所有策略"""
    db = get_mongo_db()
    
    try:
        strategies = await db["strategies"].find(
            {"user_id": current_user["id"]}
        ).sort("created_at", -1).to_list(None)
        
        # Convert ObjectId to string
        for s in strategies:
            s["id"] = str(s.pop("_id"))
        
        return ok(data={"strategies": strategies})
    except Exception as e:
        logger.error(f"获取策略失败: {e}")
        return fail(message="获取策略失败")


@router.post("/strategies/create", response_model=dict)
async def create_strategy(
    request: StrategyCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    """创建新策略（使用AI生成代码）"""
    db = get_mongo_db()
    
    try:
        # 使用AI生成策略代码
        from app.services.strategy_generator import StrategyGenerator
        
        generator = StrategyGenerator()
        strategy_code = await generator.generate_strategy(
            prompt=request.prompt,
            market=request.market
        )
        
        # 保存到数据库
        strategy = {
            "user_id": current_user["id"],
            "name": request.name,
            "description": request.prompt,
            "market": request.market,
            "code": strategy_code,
            "status": "inactive",
            "backtest_count": 0,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        result = await db["strategies"].insert_one(strategy)
        strategy["id"] = str(result.inserted_id)
        strategy.pop("_id", None)
        
        logger.info(f"✅ 用户 {current_user['id']} 创建策略: {request.name}")
        
        return ok(data={"strategy": strategy}, message="策略创建成功")
        
    except Exception as e:
        logger.error(f"创建策略失败: {e}")
        return fail(message=f"创建失败: {str(e)}")


@router.get("/strategies/{strategy_id}", response_model=dict)
async def get_strategy(
    strategy_id: str,
    current_user: dict = Depends(get_current_user)
):
    """获取策略详情"""
    db = get_mongo_db()
    
    try:
        from bson import ObjectId
        
        strategy = await db["strategies"].find_one({
            "_id": ObjectId(strategy_id),
            "user_id": current_user["id"]
        })
        
        if not strategy:
            return fail(message="策略不存在")
        
        strategy["id"] = str(strategy.pop("_id"))
        
        return ok(data={"strategy": strategy})
        
    except Exception as e:
        logger.error(f"获取策略失败: {e}")
        return fail(message="获取失败")


@router.put("/strategies/{strategy_id}", response_model=dict)
async def update_strategy(
    strategy_id: str,
    name: Optional[str] = None,
    code: Optional[str] = None,
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """更新策略"""
    db = get_mongo_db()
    
    try:
        from bson import ObjectId
        
        updates = {"updated_at": datetime.utcnow().isoformat()}
        if name:
            updates["name"] = name
        if code:
            updates["code"] = code
        if status:
            updates["status"] = status
        
        result = await db["strategies"].update_one(
            {
                "_id": ObjectId(strategy_id),
                "user_id": current_user["id"]
            },
            {"$set": updates}
        )
        
        if result.matched_count == 0:
            return fail(message="策略不存在")
        
        return ok(message="更新成功")
        
    except Exception as e:
        logger.error(f"更新策略失败: {e}")
        return fail(message="更新失败")


@router.delete("/strategies/{strategy_id}", response_model=dict)
async def delete_strategy(
    strategy_id: str,
    current_user: dict = Depends(get_current_user)
):
    """删除策略"""
    db = get_mongo_db()
    
    try:
        from bson import ObjectId
        
        result = await db["strategies"].delete_one({
            "_id": ObjectId(strategy_id),
            "user_id": current_user["id"]
        })
        
        if result.deleted_count == 0:
            return fail(message="策略不存在")
        
        # 同时删除相关的回测记录
        await db["backtests"].delete_many({"strategy_id": strategy_id})
        
        logger.info(f"✅ 删除策略: {strategy_id}")
        
        return ok(message="删除成功")
        
    except Exception as e:
        logger.error(f"删除策略失败: {e}")
        return fail(message="删除失败")


@router.post("/strategies/{strategy_id}/backtest", response_model=dict)
async def run_backtest(
    strategy_id: str,
    request: BacktestRequest,
    current_user: dict = Depends(get_current_user)
):
    """运行策略回测"""
    db = get_mongo_db()
    
    try:
        from bson import ObjectId
        from app.services.backtest_service import BacktestService
        
        # 获取策略
        strategy = await db["strategies"].find_one({
            "_id": ObjectId(strategy_id),
            "user_id": current_user["id"]
        })
        
        if not strategy:
            return fail(message="策略不存在")
        
        # 运行回测
        backtest_service = BacktestService()
        results = await backtest_service.run_backtest(
            strategy_code=strategy["code"],
            market=strategy["market"],
            start_date=request.start_date,
            end_date=request.end_date,
            initial_capital=request.initial_capital,
            commission_rate=request.commission_rate,
            slippage=request.slippage
        )
        
        # 保存回测记录
        backtest_record = {
            "strategy_id": strategy_id,
            "user_id": current_user["id"],
            "config": request.dict(),
            "results": results,
            "created_at": datetime.utcnow().isoformat()
        }
        
        await db["backtests"].insert_one(backtest_record)
        
        # 更新策略的回测次数
        await db["strategies"].update_one(
            {"_id": ObjectId(strategy_id)},
            {"$inc": {"backtest_count": 1}}
        )
        
        logger.info(f"✅ 回测完成: strategy={strategy_id}, return={results['total_return_pct']:.2f}%")
        
        return ok(data=results, message="回测完成")
        
    except Exception as e:
        logger.error(f"回测失败: {e}", exc_info=True)
        return fail(message=f"回测失败: {str(e)}")


@router.get("/strategies/{strategy_id}/backtests", response_model=dict)
async def get_backtest_history(
    strategy_id: str,
    current_user: dict = Depends(get_current_user)
):
    """获取策略的回测历史"""
    db = get_mongo_db()
    
    try:
        backtests = await db["backtests"].find({
            "strategy_id": strategy_id,
            "user_id": current_user["id"]
        }).sort("created_at", -1).to_list(None)
        
        for b in backtests:
            b["id"] = str(b.pop("_id"))
        
        return ok(data={"backtests": backtests})
        
    except Exception as e:
        logger.error(f"获取回测历史失败: {e}")
        return fail(message="获取失败")

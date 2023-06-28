import asyncio
import sys
from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat, BotCommandScopeAllPrivateChats
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import time_handlers
from config_reader import config
from middleware.db import DbSessionMiddleware
from middleware.old_buttons import CheckOldButtonCallbackMiddleware
from middleware.log import LogButtonClickCallbackMiddleware, log_worker
from routers.cheque import cheque_worker
from utils.aiogram_utils import bot, dp, scheduler
from routers import (add_wallet, admin, common_start, common_setting, mtltools, receive, trade, send, sign, swap, inout,
                     cheque)
from routers import veche, wallet_setting, common_end
from loguru import logger


# https://docs.aiogram.dev/en/latest/quick_start.html
# https://docs.aiogram.dev/en/dev-3.x/dispatcher/filters/index.html
# https://surik00.gitbooks.io/aiogram-lessons/content/chapter3.html
# https://mastergroosha.github.io/aiogram-3-guide/buttons/

# Запуск бота
@logger.catch
async def main_bot(db_pool: sessionmaker):
    logger.add("MMWB.log", rotation="1 MB", level='INFO')
    dp.callback_query.middleware(LogButtonClickCallbackMiddleware())
    dp.callback_query.middleware(CheckOldButtonCallbackMiddleware(db_pool()))
    dp.message.middleware(DbSessionMiddleware(db_pool))
    dp.callback_query.middleware(DbSessionMiddleware(db_pool))

    dp.include_router(veche.router)  # first
    dp.include_router(cheque.router)  # first
    dp.include_router(common_start.router)

    dp.include_router(sign.router)
    dp.include_router(add_wallet.router)
    dp.include_router(admin.router)
    dp.include_router(common_setting.router)
    dp.include_router(mtltools.router)
    dp.include_router(receive.router)
    dp.include_router(trade.router)
    dp.include_router(send.router)
    dp.include_router(swap.router)
    dp.include_router(wallet_setting.router)
    dp.include_router(inout.router)

    # always the last
    dp.include_router(common_end.router)

    # if 'test' in sys.argv:
    #    pass
    # else:
    scheduler.start()
    time_handlers.scheduler_jobs(scheduler, dp)

    # Запускаем бота и пропускаем все накопленные входящие
    # Да, этот метод можно вызвать даже если у вас поллинг
    await bot.delete_webhook(drop_pending_updates=True)
    await set_commands()
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


async def set_commands():
    commands_clear = []
    commands_private = [
        BotCommand(
            command="start",
            description="Start or ReStart bot",
        ),
        BotCommand(
            command="change_wallet",
            description="Switch to another address",
        ),
        BotCommand(
            command="send",
            description="Send tokens",
        ),
    ]
    if 'test' in sys.argv:
        commands_private.append(BotCommand(
            command="delete_all",
            description="Delete all data",
        ))
    commands_admin = commands_private + [
        BotCommand(
            command="restart",
            description="ReStart bot",
        ),
        BotCommand(
            command="fee",
            description="check fee",
        ),
    ]

    await bot.set_my_commands(commands=commands_clear, scope=BotCommandScopeDefault())
    await bot.set_my_commands(commands=commands_private, scope=BotCommandScopeAllPrivateChats())
    await bot.set_my_commands(commands=commands_admin, scope=BotCommandScopeChat(chat_id=84131737))


async def main():
    # Запуск бота
    engine = create_engine(config.db_dns, pool_pre_ping=True)
    # Creating DB connections pool
    db_pool = sessionmaker(bind=engine)
    await asyncio.gather(asyncio.create_task(main_bot(db_pool)),
                         asyncio.create_task(cheque_worker(db_pool())),
                         asyncio.create_task(log_worker(db_pool())),
                         return_exceptions=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.error("Exit")

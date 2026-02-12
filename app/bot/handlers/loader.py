# app/bot/loader.py
import os
import sys
import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils import executor

# Для Windows специфичных проблем с asyncio
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Получаем конфигурацию
try:
    from app.bot.config import BOT_TOKEN, ADMIN_IDS, MASTER_GROUP_ID
    logger.info("✅ Конфигурация загружена")
    logger.info(f"👑 Админы: {ADMIN_IDS}")
except ImportError as e:
    logger.error(f"❌ Ошибка импорта конфигурации: {e}")
    raise
except Exception as e:
    logger.error(f"❌ Ошибка при загрузке конфигурации: {e}")
    raise

# Проверяем наличие токена
if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN":
    logger.error("❌ BOT_TOKEN не установлен! Проверьте файл config.py")
    sys.exit(1)

# Создаем бота (для aiogram 2.x без сессии)
try:
    bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
    logger.info("✅ Бот создан")
except Exception as e:
    logger.error(f"❌ Ошибка при создании бота: {e}")
    sys.exit(1)

# Создаем хранилище и диспетчер
try:
    storage = MemoryStorage()
    dp = Dispatcher(bot, storage=storage)
    logger.info("✅ Диспетчер создан")
except Exception as e:
    logger.error(f"❌ Ошибка при создании диспетчера: {e}")
    sys.exit(1)

def load_handlers():
    """Загрузка всех обработчиков"""
    try:
        from app.bot.handlers import register_all_handlers
        register_all_handlers(dp)
        logger.info("✅ Все обработчики успешно зарегистрированы")
        return True
    except ImportError as e:
        logger.error(f"❌ Ошибка импорта обработчиков: {e}")
        logger.info("Проверьте структуру папок и файлы handlers/")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        logger.error(f"❌ Ошибка при загрузке обработчиков: {e}")
        import traceback
        traceback.print_exc()
        return False

async def on_startup(_):
    """Действия при запуске бота"""
    logger.info("🚀 Бот запускается...")
    
    try:
        # Получаем информацию о боте
        bot_info = await bot.get_me()
        logger.info(f"🤖 Бот: @{bot_info.username} (ID: {bot_info.id})")
        logger.info(f"👑 Админы: {ADMIN_IDS}")
        if MASTER_GROUP_ID:
            logger.info(f"👥 Группа мастеров: {MASTER_GROUP_ID}")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось получить информацию о боте: {e}")

async def on_shutdown(_):
    """Действия при остановке бота"""
    logger.info("🛑 Бот останавливается...")
    try:
        await dp.storage.close()
        await dp.storage.wait_closed()
        await bot.close()
    except Exception as e:
        logger.warning(f"⚠️ Ошибка при закрытии соединений: {e}")

def start_bot():
    """Запуск Telegram бота"""
    max_retries = 10
    retry_delay = 10
    
    for attempt in range(max_retries):
        try:
            logger.info(f"🔧 Попытка запуска {attempt + 1}/{max_retries}")
            
            # Загружаем обработчики
            if not load_handlers():
                logger.error("❌ Не удалось загрузить обработчики")
                if attempt >= max_retries - 1:
                    logger.error("🚫 Достигнут лимит попыток")
                    break
                logger.info(f"⏳ Повтор через {retry_delay} секунд...")
                continue
            
            # Запускаем polling через executor
            logger.info("🔄 Бот ожидает сообщений...")
            
            # Используем executor из aiogram 2.x
            executor.start_polling(
                dp,
                skip_updates=True,
                timeout=30,
                relax=0.5,
                fast=False,
                on_startup=on_startup,
                on_shutdown=on_shutdown
            )
            
            logger.info("✅ Поллинг завершен нормально")
            break
            
        except KeyboardInterrupt:
            logger.info("⏹️ Остановка по команде пользователя")
            break
        except SystemExit:
            logger.info("⏹️ Системный выход")
            break
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            
            # Классифицируем ошибки
            if any(keyword in error_msg.lower() or keyword in error_type.lower() 
                   for keyword in ['network', 'connect', 'disconnect', 'timeout', 'ssl']):
                logger.warning(f"🌐 Сетевая ошибка: {error_type}: {error_msg}")
            elif 'forbidden' in error_msg.lower() or 'unauthorized' in error_msg.lower():
                logger.error(f"🔒 Ошибка авторизации: {error_msg}")
                logger.error("Проверьте BOT_TOKEN в config.py")
                break
            else:
                logger.error(f"❌ Критическая ошибка: {error_type}: {error_msg}")
                import traceback
                traceback.print_exc()
            
            # Проверяем, нужно ли продолжать попытки
            if attempt < max_retries - 1:
                next_delay = retry_delay * min(attempt + 1, 3)
                logger.info(f"⏳ Повтор через {next_delay} секунд...")
                import time
                time.sleep(next_delay)
            else:
                logger.error(f"🚫 Достигнут лимит {max_retries} попыток. Бот остановлен.")
                break

async def test_bot():
    """Тестирование подключения бота"""
    try:
        logger.info("🧪 Тестирование подключения бота...")
        bot_info = await bot.get_me()
        logger.info(f"✅ Тест пройден: Бот @{bot_info.username}")
        return True
    except Exception as e:
        logger.error(f"❌ Тест не пройден: {e}")
        return False

if __name__ == "__main__":
    # Прямой запуск для тестирования
    logger.info("🔧 Прямой запуск loader.py")
    
    # Запускаем тест и бот
    try:
        # Тестируем подключение
        loop = asyncio.get_event_loop()
        test_result = loop.run_until_complete(test_bot())
        
        if test_result:
            start_bot()
        else:
            logger.error("❌ Не удалось подключиться к Telegram API")
    except KeyboardInterrupt:
        logger.info("👋 Завершено по Ctrl+C")
    except Exception as e:
        logger.error(f"💥 Фатальная ошибка: {e}")

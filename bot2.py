from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import SessionPasswordNeeded
import asyncio
from database import Database
import os
from datetime import datetime

# Bot configuration
API_ID = 22359038
API_HASH = "b3901895dc193c30c808ba4f1b550ed0"
BOT_TOKEN = "8175825591:AAH-OjjSS19fTEyvKhSu5UjJ3vT1TyOdLtQ"

# Admin user IDs
ADMIN_USERS = [5531461861]

# Initialize the bot and database
app = Client("auto_accept_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
db = Database()

# Welcome message configuration
WELCOME_MESSAGE = "Welcome to our channel! Thank you for joining."
WELCOME_BUTTON_TEXT = "Visit our website"
WELCOME_BUTTON_URL = "https://example.com"

# Store user states
user_states = {}

def admin_filter(_, __, message):
    return message.from_user and message.from_user.id in ADMIN_USERS

admin_only = filters.create(admin_filter)

@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    user_id = message.from_user.id
    session_data = db.get_session(user_id)
    
    if not session_data or not session_data['session_string']:
        await message.reply_text(
            "Welcome! To use this bot, you need to add your Pyrogram session string.\n"
            "Please send your session string to continue."
        )
        user_states[user_id] = {'state': 'waiting_for_session'}
    else:
        if not session_data['channel_id']:
            await message.reply_text(
                "Please send your channel ID to start accepting requests."
            )
            user_states[user_id] = {'state': 'waiting_for_channel'}
        else:
            await message.reply_text(
                "Press 'Start' to begin approving requests.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Start", callback_data="start_requests")]
                ])
            )

@app.on_message(filters.text & filters.private & ~filters.command())
async def handle_session_input(client, message):
    user_id = message.from_user.id
    
    if user_id not in user_states:
        await start_command(client, message)
        return

    state = user_states[user_id]['state']
    
    if state == 'waiting_for_session':
        session_string = message.text.strip()
        
        try:
            temp_client = Client(
                name="temp",
                api_id=API_ID,
                api_hash=API_HASH,
                session_string=session_string,
                in_memory=True
            )
            
            await temp_client.start()
            await temp_client.stop()
            
            db.save_session(user_id, session_string)
            
            await message.reply_text(
                "Session added successfully! Now, please send your channel ID."
            )
            user_states[user_id] = {'state': 'waiting_for_channel'}
            
        except Exception as e:
            await message.reply_text(
                "Invalid session string. Please send a valid Pyrogram session string."
            )
            return
            
    elif state == 'waiting_for_channel':
        try:
            channel_id = int(message.text)
            
            session_data = db.get_session(user_id)
            user_client = Client(
                name=f"user_{user_id}",
                api_id=API_ID,
                api_hash=API_HASH,
                session_string=session_data['session_string'],
                in_memory=True
            )
            
            await user_client.start()
            chat = await user_client.get_chat(channel_id)
            await user_client.stop()
            
            db.update_channel_id(user_id, channel_id)
            
            await message.reply_text(
                "Channel ID set successfully! Press 'Start' to begin approving requests.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Start", callback_data="start_requests")]
                ])
            )
            user_states[user_id] = {'state': 'ready'}
            
        except ValueError:
            await message.reply_text("Please send a valid numeric channel ID.")
        except Exception as e:
            await message.reply_text(f"Error: Could not access the channel. Make sure the ID is correct and you have proper access.")

@app.on_callback_query(filters.regex("^start_requests$"))
async def start_approving(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    session_data = db.get_session(user_id)
    
    if not session_data or not session_data['session_string']:
        await callback_query.message.reply_text("Please add your session string first using /start")
        return
        
    if not session_data['channel_id']:
        await callback_query.message.reply_text("Please set your channel ID first using /start")
        return

    progress_message = await callback_query.message.reply_text("Starting to approve join requests...")
    
    try:
        user_client = Client(
            name=f"user_{user_id}",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=session_data['session_string'],
            in_memory=True
        )
        
        await user_client.start()
        
        total_approved = 0
        total_declined = 0
        start_time = datetime.now()

        while True:
            try:
                requests = []
                async for request in user_client.get_chat_join_requests(session_data['channel_id'], limit=100):
                    requests.append(request)

                if not requests:
                    break

                for request in requests:
                    try:
                        await user_client.approve_chat_join_request(
                            chat_id=session_data['channel_id'],
                            user_id=request.user.id
                        )
                        total_approved += 1

                        db.add_user(
                            request.user.id,
                            request.user.username,
                            request.user.first_name,
                            request.user.last_name
                        )

                        try:
                            welcome_keyboard = InlineKeyboardMarkup([
                                [InlineKeyboardButton(WELCOME_BUTTON_TEXT, url=WELCOME_BUTTON_URL)]
                            ])
                            
                            await app.send_message(
                                request.user.id,
                                WELCOME_MESSAGE,
                                reply_markup=welcome_keyboard
                            )
                        except Exception as e:
                            print(f"Error sending welcome message: {e}")

                    except Exception as e:
                        if "USER_CHANNELS_TOO_MUCH" in str(e):
                            try:
                                await user_client.decline_chat_join_request(
                                    chat_id=session_data['channel_id'],
                                    user_id=request.user.id
                                )
                                total_declined += 1
                            except Exception as decline_error:
                                print(f"Error declining request: {decline_error}")
                        else:
                            print(f"Error handling request: {e}")

                    if (total_approved + total_declined) % 10 == 0:
                        elapsed_time = (datetime.now() - start_time).total_seconds()
                        rate = (total_approved + total_declined) / elapsed_time if elapsed_time > 0 else 0
                        await progress_message.edit_text(
                            f"Processing requests...\n"
                            f"Approved: {total_approved}\n"
                            f"Declined: {total_declined}\n"
                            f"Rate: {rate:.2f} requests/second"
                        )

                await asyncio.sleep(1)

            except Exception as e:
                print(f"Error fetching requests: {e}")
                await asyncio.sleep(5)

        await user_client.stop()

        elapsed_time = (datetime.now() - start_time).total_seconds()
        rate = (total_approved + total_declined) / elapsed_time if elapsed_time > 0 else 0
        
        await progress_message.edit_text(
            f"Finished processing requests.\n"
            f"Final Statistics:\n"
            f"Approved: {total_approved}\n"
            f"Declined: {total_declined}\n"
            f"Average Rate: {rate:.2f} requests/second\n"
            f"Total Time: {int(elapsed_time)}s"
        )

    except Exception as e:
        await progress_message.edit_text(f"Error occurred: {str(e)}")

@app.on_message(filters.command("total") & filters.private & admin_only)
async def total_users(client, message):
    total = db.get_total_users()
    await message.reply_text(f"Total number of users: {total}")

@app.on_message(filters.command("broadcast") & filters.private & admin_only)
async def broadcast_command(client, message):
    if len(message.command) < 2:
        await message.reply_text("Please use the format: /broadcast your_message")
        return

    broadcast_message = " ".join(message.command[1:])
    user_ids = db.get_all_user_ids()
    
    success_count = 0
    fail_count = 0

    progress_msg = await message.reply_text("Broadcasting message...")

    for user_id in user_ids:
        try:
            await client.send_message(user_id, broadcast_message)
            success_count += 1
        except Exception as e:
            print(f"Failed to send message to {user_id}: {e}")
            fail_count += 1

        if (success_count + fail_count) % 10 == 0:
            await progress_msg.edit_text(
                f"Progress: {success_count + fail_count}/{len(user_ids)}"
            )

    await progress_msg.edit_text(
        f"Broadcast completed!\nSuccess: {success_count}\nFailed: {fail_count}"
    )

@app.on_error()
async def error_handler(client, error):
    print(f"An error occurred: {error}")

if __name__ == "__main__":
    print("Bot is starting...")
    try:
        app.run()
    finally:
        db.close() 

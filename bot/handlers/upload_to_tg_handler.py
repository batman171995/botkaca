# GOAL:
# getting track for logging

import logging

LOGGER = logging.getLogger(__name__)

# GOAL:
# universal function for uploading file to telegram

from os import path as os_path, listdir as os_lisdir, remove as os_remove, rmdir as os_rmdir
from time import time
from math import floor
from pyrogram import Message
import ffmpeg
from bot import LOCAL, CONFIG
from bot.plugins import formater, split, thumbnail_video

async def func(filepath: str, message: Message, delete=False):
    if not os_path.exists(filepath):
        LOGGER.error(f'File not found : {filepath}')
        await message.edit_text(
            LOCAL.UPLOAD_FAILED_FILE_MISSING.format(
                name = os_path.basename(filepath)
            )
        )
        return

    if os_path.isdir(filepath):
        ls = os_lisdir(filepath)
        async for filepath in ls:
            await message.edit(
                LOCAL.UPLOADING_FILE.format(
                    name = os_path.basename(filepath)
                )
            )
            await func(filepath, message, delete)
        if delete:
            os_rmdir(filepath)
        return

    video = ['.mp4','.mkv','.avi','.webm','.wmv','.mov']
    photo = ['.jpg','.jpeg','.png']

    file_ext = os_path.splitext(filepath)[1].lower()
    LOGGER.debug(f'Uploading : {filepath}')

    upload_fn = None
    split_fn = None
    if file_ext in photo:
        upload_fn = message.reply_photo
        split_fn = split.func
    elif file_ext in video:
        split_fn = split.video

        probe = ffmpeg.probe(filepath)
        video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
        duration = int(float(video_stream["duration"])) or 0
        width = int(video_stream['width']) or 0
        height = int(video_stream['height']) or 0

        thumbnail = thumbnail_video.func(filepath)
        upload_fn = lambda file, **kwargs: await message.reply_video(
            file, 
            supports_streaming=True,
            thumb=thumbnail,
            height=height,
            width=width,
            **kwargs
        )
    else:
        upload_fn = message.reply_document
        split_fn = split.func
    
    if os_path.getsize(filepath) > int(CONFIG.UPLOAD_MAX_SIZE):
        LOGGER.warning(f'File too large : {filepath}')
        await message.edit_text(
            LOCAL.SPLIT_FILE.format(
                name = os_path.basename(filepath)
            )
        )
        splited = await split_fn(filepath, int(CONFIG.UPLOAD_MAX_SIZE))
        if not splited:
            await message.edit(
                LOCAL.SPLIT_FAILED.format(
                    name = os_path.basename(filepath)
                )
            )
            return
        for filepath in splited:
            await message.edit(
                LOCAL.UPLOADING_FILE.format(
                    name = os_path.basename(filepath)
                )
            )
            await func(filepath, message, delete=True)
        return False
    
    info = {
        "time" : time(),
        "name" : os_path.basename(filepath),
        "last_update" : 0,
        "prev_text" : ""
    }
    await upload_fn(
        filepath,
        disable_notification=True,
        progress=progress_upload_tg,
        progress_args=(
            message,
            info
        ),
        caption=os_path.basename(filepath)
    )            
    LOGGER.debug(f'Uploaded : {filepath}')
    if delete:
        if thumbnail:
            os_remove(thumbnail)
        os_remove(filepath)

async def progress_upload_tg(current, total, message, info):
    percentage = round(current * 100 / total)
    block = ""
    for i in range(1, 11):
        if i <= floor(percentage/10):
            block += LOCAL.BLOCK_FILLED
        else:
            block += LOCAL.BLOCK_EMPTY
    time_passed = time() - info["time"]
    up_speed = current / time_passed
    text = LOCAL.UPLOADING_PROGRESS.format(
            name = info["name"],
            block = block,
            size = formater.format_bytes(total),
            upload_speed = formater.format_bytes(up_speed),
            eta = formater.format_time((total - current)/up_speed)
        )
    if text != info["prev_text"] and (time() - info["last_update"]) >= int(CONFIG.EDIT_SLEEP):
        await message.edit(text)
        info.update({
            "prev_text" : text,
            "last_update" : time()
        })
import os
import logging
import re
import shutil

import wget

from dotenv import load_dotenv
from telegram import Update, InputMediaPhoto, InputMediaVideo
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler
from telegram.ext.filters import MessageFilter

from pytube import YouTube
from pytube import exceptions

from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.common.exceptions import NoSuchElementException, WebDriverException

# ----------------- CONFIGS -----------------

load_dotenv()


class Config(object):
    _instance = None
    token = os.getenv('TOKEN')
    instagram_username = os.getenv('INSTAGRAM_USERNAME')
    instagram_password = os.getenv('INSTAGRAM_PASSWORD')

    def __new__(self):
        if self._instance is None:
            self._instance = super(Config, self).__new__(self)

        return self._instance


logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ----------------- FILTERS -----------------


class YouTubeFilter(MessageFilter):
    YT_REGEX = '^((?:https?:)?\/\/)?((?:www|m)\.)?((?:youtube(-nocookie)?\.com|youtu.be))(\/(?:[\w\-]+\?v=|embed\/|v\/)?)([\w\-]+)(\S+)?$'

    def filter(self, msg) -> bool:
        return re.search(self.YT_REGEX, msg.text)


class InstagramFilter(MessageFilter):
    INSTA_REGEX = '/((?:https?:\/\/)?(?:www\.)?instagram\.com\/(?:p|reel|story|tv)\/([^/?#&]+))'

    def filter(self, msg) -> bool:
        return re.search(self.INSTA_REGEX, msg.text)


# ----------------- FUNCTIONALITIES -----------------

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    caption = '''
    ✨Awesome Downloader✨
    A completely free Telegram bot for downloading videos and pictures from different streaming services and social medias.
        
        
    🔵 Currently supported servers:
    ✔️ YouTube
    ✔️ Instagram
    
    
    ❔ Need help? /help
    
    
    📎 t.me/awesome_downloader_bot
    '''.replace('    ', '')
    await ctx.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=open('./images/logo.png', 'rb'),
        caption=caption
    )


async def help_(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = '''
    ✨Awesome Downloader✨
    How to use:
    copy-paste the URL and wait for the bot to response
    
    Errors
    - Requested URL does not exist - check the URL again
    - Video is not available - requested video is age-restricted, live stream, private, or... and can't be downloaded.
    - Unknow error accoured - something unexcepted happend.
    - Couldn\'t fetch Instagram - there is nothing that you can do, just try another time =)
    '''.replace('    ', '')
    await ctx.bot.send_message(chat_id=update.effective_chat.id, text=text)
    

async def yt_downloader(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # BASIC MESSAGE INFO
    chat_id = update.effective_chat.id
    msg_id = update.message.message_id

    # VIDEO INFO
    url: str = update.message.text
    video_link: str = url.split('/')[-1].split('?')[0]
    output_path = f'./outputs/{video_link}.mp4'

    try:
        status_msg = await ctx.bot.send_message(chat_id=chat_id, reply_to_message_id=msg_id, text='🔎 Finding Video...')
        streams = YouTube(url).streams.filter(file_extension='mp4')

        await ctx.bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text='🔽 Downloading...')
        streams.first().download(
            output_path='outputs/yt',
            filename=f'{video_link}.mp4'
        )

        await ctx.bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text='✨ Sending...')
        await ctx.bot.send_video(
            chat_id=chat_id,
            video=open(output_path, 'rb'),
            reply_to_message_id=msg_id,
            supports_streaming=True
        )
        os.remove(output_path)

    except exceptions.RegexMatchError:
        await ctx.bot.send_message(
            chat_id=chat_id,
            reply_to_message_id=msg_id,
            text='❌ Requested URL does not exist.'
        )

    except exceptions.VideoUnavailable:
        await ctx.bot.send_message(
            chat_id=chat_id,
            reply_to_message_id=msg_id,
            text='❌ Video is not available.\n Click /help to learn more...'
        )

    await ctx.bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)


async def insta_downloader(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # BASIC MESSAGE INFO
    chat_id = update.effective_chat.id
    msg_id = update.message.message_id

    # CONFIG URL
    url = update.message.text.split('?')[0]
    route = url[25:]
    address = 'https://www.instagram.com/accounts/login/?next=' + route

    # OUTPUT
    link = url.split('/')[-2]
    output_path = f'./outputs/{link}'

    service = Service('./geckodriver')
    opts = webdriver.FirefoxOptions()
    opts.add_argument('--disable-gpu')
    opts.add_argument("--no-sandbox")
    opts.add_argument("--headless")
    driver = webdriver.Firefox(service=service, options=opts)
    try:
        status_msg = await ctx.bot.send_message(chat_id=chat_id, reply_to_message_id=msg_id, text='🔎 Processing...')
        driver.get(address)
        try:
            # Allowing essential cookies - instagram popup
            driver.find_element(by='css selector',
                                value='button.aOOlW.HoLwm').click()
        except NoSuchElementException:
            pass

        try:
            # Logging in - wait for login form to get loaded
            WebDriverWait(driver, 10).until(
                expected_conditions.presence_of_element_located(
                    (By.CSS_SELECTOR, 'form#loginForm'),
                )
            )
            # Fill out the inputs
            driver.find_element(by='name', value='username')\
                .send_keys(Config().instagram_username)
            driver.find_element(by='name', value='password')\
                .send_keys(Config().instagram_password)
        finally:
            # Login
            while True:
                try:
                    driver.find_element(
                        by='css selector',
                        value='button[type=submit]'
                    ).click()
                    break
                except WebDriverException:
                    pass

        try:
            WebDriverWait(driver, 10).until(
                expected_conditions.text_to_be_present_in_element(
                    (By.CSS_SELECTOR, 'button.sqdOP.yWX7d.y3zKF'),
                    'Not now'
                )
            )
        except NoSuchElementException:
            await ctx.bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
            await ctx.bot.send_message(chat_id=chat_id, reply_to_message_id=msg_id, text='❌ Couldn\'t fecth Instagram, please try again another time.')
            logging.error('Failed to login.')
            driver.quit()
            return
        finally:
            driver.find_element(
                by='css selector',
                value='button.sqdOP.yWX7d.y3zKF'
            ).click()

        await ctx.bot.edit_message_text('✂️ Fetching...', chat_id=chat_id, message_id=status_msg.message_id)
        try:
            # Current content/post/story/reel/etc has a class of ._aagu
            WebDriverWait(driver, 25).until(
                expected_conditions.presence_of_element_located(
                    (By.CSS_SELECTOR, '._aagu')
                )
            )
        except:
            await ctx.bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
            await ctx.bot.send_message(chat_id=chat_id, reply_to_message_id=msg_id, text='❌ Requested URL does not exist.')
            logging.error(f'Couldn\'t fetch URL {url}.')
            driver.quit()
            return
        finally:
            # All videos have a class of _ab1d
            vid_urls = driver.find_elements(
                'css selector',
                '._aagu._aamh video._ab1d, ._aatn video._ab1d'
            )
            # All images have a class of _aagt
            img_urls = driver.find_elements(
                'css selector',
                '._aagu._aamh img._aagt, ._aatn img._aagt'
            )

            media_urls = [
                media.get_property('src')
                for media in vid_urls + img_urls
            ]
            # Only videos have type attr(it's always mp4), for images, the extension is always jpg
            media_types = [
                media.get_attribute('type').split('/')[-1]
                if media.get_attribute('type')
                else 'jpg'
                for media in vid_urls + img_urls
            ]
            if len(media_urls) == 2:
                try:
                    # If there be more than 2 media in a post, we should press the next button unitle we reach the last one and scarpe all of images/videos
                    next_btn = driver.find_element('css selector', '._9zm2')
                    next_btn.click()
                    while True:
                        next_btn = driver.find_element(
                            'css selector', '._9zm2')
                        next_btn.click()
                        new_url = driver.find_elements(
                            'css selector', '._aagu._aamh video._ab1d, ._aagu._aamh img._aagt, ._aatn img._aagt, ._aatn video._ab1d')[-1]
                        media_urls.append(new_url.get_property('src'))
                        media_types.append(
                            new_url.get_attribute('type').split('/')[-1]
                            if new_url.get_attribute('type')
                            else 'jpg'
                        )
                except NoSuchElementException:
                    pass

        medias = []
        os.mkdir(output_path)
        for index, src in enumerate(media_urls):
            await ctx.bot.edit_message_text(f'🔽 [{index + 1}/{len(media_urls)}] Downloading...', chat_id=chat_id, message_id=status_msg.message_id)
            extension = media_types[index]
            wget.download(src, f'{output_path}/{index}.{extension}')

            match extension:
                case 'mp4':
                    medias.append(InputMediaVideo(
                        open(f'{output_path}/{index}.{extension}', 'rb')
                    ))
                case 'jpg':
                    medias.append(InputMediaPhoto(
                        open(f'{output_path}/{index}.{extension}', 'rb')
                    ))

        await ctx.bot.edit_message_text(f'✨ Sending...', chat_id=chat_id, message_id=status_msg.message_id)
        await ctx.bot.send_media_group(chat_id=chat_id, reply_to_message_id=msg_id, media=medias)

    except Exception as e:
        await ctx.bot.send_message(chat_id=chat_id, reply_to_message_id=msg_id, text='❌ Unknow error accoured, please try another time.')
        logging.error(f'Unknown error accoured: {str(e)}')

    await ctx.bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
    if os.path.isdir(output_path):
        shutil.rmtree(output_path)
    driver.quit()


if __name__ == '__main__':
    if not os.path.isdir('./outputs'):
        # create outputs directory if it isnot created(you are running tyhe code for the first time)
        os.mkdir('./outputs')
        
    app = ApplicationBuilder().token(Config().token).build()

    yt_filter = YouTubeFilter()
    insta_filter = InstagramFilter()

    start_handler = CommandHandler('start', start)
    help_handler = CommandHandler('help', help_)
    yt_handler = MessageHandler(yt_filter, yt_downloader)
    insta_handler = MessageHandler(insta_filter, insta_downloader)

    app.add_handlers([
        start_handler,
        help_handler,
        yt_handler,
        insta_handler
    ])

    app.run_polling()

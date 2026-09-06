import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
import os
from PIL import Image, ImageOps, ImageEnhance

# Ваш токен
API_TOKEN = '8513010692:AAHfbdthnd6IJocW-oNGPJbw2IlI4xlQHPs'
bot = telebot.TeleBot(API_TOKEN)

os.makedirs("downloads", exist_ok=True)
os.makedirs("transfers", exist_ok=True)
os.makedirs("try_on", exist_ok=True)

user_data = {}

def get_main_menu_inline():
    kb = InlineKeyboardMarkup()
    kb.row(
        InlineKeyboardButton(text="🖨 Трансфер", callback_data="create_stencil"),
        InlineKeyboardButton(text="🖼 Примерка", callback_data="try_on")
    )
    return kb

def get_back_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    markup.add(KeyboardButton("🏠 Главное меню"))
    return markup

@bot.message_handler(commands=['start'])
def cmd_start(message):
    if message.chat.id in user_data:
        del user_data[message.chat.id]
        
    bot.send_message(
        message.chat.id,
        "Студия screw tattoo ink на связи. Выберите действие:",
        reply_markup=get_main_menu_inline()
    )

@bot.message_handler(func=lambda message: message.text == "🏠 Главное меню")
def back_to_menu(message):
    if message.chat.id in user_data:
        del user_data[message.chat.id]
    bot.send_message(
        message.chat.id,
        "Возвращаемся в главное меню:",
        reply_markup=get_main_menu_inline()
    )

@bot.callback_query_handler(func=lambda call: True)
def handle_buttons(call):
    bot.answer_callback_query(call.id)
    
    if call.data == "create_stencil":
        msg = bot.send_message(
            call.message.chat.id, 
            "Отправьте картинку (эскиз) для создания трансфера:",
            reply_markup=get_back_keyboard()
        )
        bot.register_next_step_handler(msg, process_stencil)
        
    elif call.data == "try_on":
        msg = bot.send_message(
            call.message.chat.id, 
            "Шаг 1/2: Отправьте сначала ЭСКИЗ будущей татуировки:",
            reply_markup=get_back_keyboard()
        )
        bot.register_next_step_handler(msg, process_try_on_get_sketch)

def download_photo(message):
    if message.content_type != 'photo':
        return None
    file_id = message.photo[-1].file_id
    file_info = bot.get_file(file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    
    file_path = f"downloads/{message.chat.id}_{file_id}.jpg"
    with open(file_path, 'wb') as new_file:
        new_file.write(downloaded_file)
    return file_path

def create_transfer_pillow(input_path, output_path):
    img = Image.open(input_path)
    gray_img = img.convert("L")
    enhancer = ImageEnhance.Contrast(gray_img)
    contrast_img = enhancer.enhance(2.0)
    inverted_img = ImageOps.invert(contrast_img)
    inverted_img.save(output_path)

def process_stencil(message):
    if message.text == "🏠 Главное меню":
        back_to_menu(message)
        return

    input_path = download_photo(message)
    if not input_path:
        msg = bot.send_message(message.chat.id, "Пожалуйста, отправьте именно фотографию эскиза:")
        bot.register_next_step_handler(msg, process_stencil)
        return
    
    bot.send_message(message.chat.id, "Генерирую трансфер...")
    output_path = f"transfers/transfer_{message.chat.id}.png"
    
    try:
        create_transfer_pillow(input_path, output_path)
        with open(output_path, 'rb') as transfer_file:
             bot.send_document(message.chat.id, transfer_file, caption="Готовый трансфер! 🖨")
        bot.send_message(message.chat.id, "Что делаем дальше?", reply_markup=get_main_menu_inline())
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка: {e}", reply_markup=get_main_menu_inline())

def process_try_on_get_sketch(message):
    if message.text == "🏠 Главное меню":
        back_to_menu(message)
        return

    input_path = download_photo(message)
    if not input_path:
        msg = bot.send_message(message.chat.id, "Пожалуйста, отправьте картинку эскиза:")
        bot.register_next_step_handler(msg, process_try_on_get_sketch)
        return
    
    user_data[message.chat.id] = {"sketch": input_path}
    
    msg = bot.send_message(
        message.chat.id, 
        "Эскиз принят! ✅\n\nШаг 2/2: Теперь отправьте **фотографию части тела**, куда нужно примерить татуировку:",
        reply_markup=get_back_keyboard()
    )
    bot.register_next_step_handler(msg, process_try_on_get_body)

def process_try_on_get_body(message):
    if message.text == "🏠 Главное меню":
        back_to_menu(message)
        return

    body_path = download_photo(message)
    if not body_path:
        msg = bot.send_message(message.chat.id, "Пожалуйста, отправьте фотографию тела:")
        bot.register_next_step_handler(msg, process_try_on_get_body)
        return
    
    sketch_path = user_data.get(message.chat.id, {}).get("sketch")
    if not sketch_path:
        bot.send_message(message.chat.id, "Произошла ошибка сессии. Начните сначала.", reply_markup=get_main_menu_inline())
        return

    bot.send_message(message.chat.id, "Примеряю эскиз на фото...")

    try:
        body_img = Image.open(body_path).convert("RGBA")
        sketch_img = Image.open(sketch_path).convert("RGBA")
        
        datas = sketch_img.getdata()
        new_data = []
        for item in datas:
            if item[0] > 200 and item[1] > 200 and item[2] > 200:
                new_data.append((255, 255, 255, 0))
            else:
                new_data.append((70, 90, 180, 200)) 
        sketch_img.putdata(new_data)

        body_w, body_h = body_img.size
        sketch_w = body_w // 3
        w_percent = (sketch_w / float(sketch_img.size[0]))
        sketch_h = int((float(sketch_img.size[1]) * float(w_percent)))
        sketch_img = sketch_img.resize((sketch_w, sketch_h), Image.Resampling.LANCZOS)

        paste_x = (body_w - sketch_w) // 2
        paste_y = (body_h - sketch_h) // 2
        
        body_img.paste(sketch_img, (paste_x, paste_y), sketch_img)

        output_path = f"try_on/result_{message.chat.id}.png"
        body_img.convert("RGB").save(output_path)

        with open(output_path, 'rb') as result_file:
            bot.send_photo(message.chat.id, result_file, caption="Вот что получилось! Примерка завершена 🎨")

        if message.chat.id in user_data:
            del user_data[message.chat.id]
            
        bot.send_message(message.chat.id, "Выберите дальнейшее действие:", reply_markup=get_main_menu_inline())

    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при примерке: {e}", reply_markup=get_main_menu_inline())

if __name__ == '__main__':
    print("Бот студии screw tattoo ink запущен в облаке...")
    bot.polling(none_stop=True)

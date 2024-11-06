import json
import time
import shutil
import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from ebooklib import epub
from PIL import Image
import os

key = b"xxxmanga.woo.key"
from bs4 import BeautifulSoup


def aes_cbc_decrypt(ciphertext, key, iv):
    cipher = AES.new(key, AES.MODE_CBC, iv)
    decrypted = unpad(cipher.decrypt(ciphertext), AES.block_size)
    return decrypted.decode('utf-8')


def analyze_data(enc_data):
    ciphertext = string_to_hex(enc_data[16:])
    iv = enc_data[:16].encode('utf-8')
    return json.loads(aes_cbc_decrypt(ciphertext, key, iv))


def string_to_hex(input_string):
    return bytes.fromhex(input_string)


def get_comic_detail(comic_name):
    while True:
        try:
            response = requests.get("https://www.copymanga.tv/comic/" + comic_name).content
            soup = BeautifulSoup(response, 'html.parser')
            comic_data = soup.find_all(attrs={"class": "comicParticulars-right-txt"})
            return comic_data[0].text.strip(), comic_data[1].text.strip()
        except Exception as e:
            time.sleep(7)


def get_chapters(comic_name):
    while True:
        try:
            response = requests.get(f"https://www.copymanga.tv/comicdetail/{comic_name}/chapters").json()
            return analyze_data(str(response['results']))
        except Exception as e:
            time.sleep(7)


def get_chapter_images(chapter_id):
    while True:
        try:
            response = requests.get(f"https://www.copymanga.tv/comic/tianguodamojing/chapter/{chapter_id}").content
            data = analyze_data(
                BeautifulSoup(response, 'html.parser').find(name="div", attrs={"class": "imageData"}).attrs[
                    'contentkey'])
            return [i['url'] for i in data]
        except Exception as e:
            time.sleep(7)


def filter_list(input_list, condition):
    return [item for item in input_list if condition(item)]


def images_to_epub(image_paths, output_file, id, title, book_name, author=""):
    path = f"images/{book_name}/{id}"
    os.makedirs(path, exist_ok=True)
    image_names = []
    for url in image_paths:
        while True:
            try:
                response = requests.get(url)
                break
            except Exception as e:
                time.sleep(5)
        if response.status_code == 200:
            image_name = url.split("/")[-1]
            with open(os.path.join(path, image_name), "wb") as file:
                file.write(response.content)
            image_names.append(image_name)
            time.sleep(5)

        else:
            print(f"download error: {url}")

    book = epub.EpubBook()
    book.set_identifier(str(id))
    book.set_title(title)
    book.set_language('en')
    book.add_author(author)
    for i in range(len(image_names)):
        img = Image.open(path + "/" + image_names[i])
        img = img.convert('RGB')
        img.save(f'image_{i}.jpg')

        img_item = epub.EpubItem(uid=f'image_{i}', file_name=f'image_{i}.jpg', media_type='image/jpeg')
        with open(f'image_{i}.jpg', 'rb') as f:
            img_item.set_content(f.read())
            if i == 0:
                book.add_item(epub.EpubItem(uid="cover", file_name=f"image_{i}.jpg", media_type='image/jpeg',
                                            content=f.read()))
        book.add_item(img_item)

        chapter = epub.EpubHtml(title=f'Image {i}', file_name=f'chap_{i}.xhtml', lang='en')
        chapter.set_content(f'<html><body><img src="{img_item.file_name}" /></body></html>')
        book.add_item(chapter)
        book.spine.append(chapter)
    nav = epub.EpubNav()
    book.add_item(nav)
    epub.write_epub(output_file, book)

    for z in range(len(image_names)):
        os.remove(f'image_{z}.jpg')


if __name__ == "__main__":
    book_name = input("please enter manga name: ")
    comic_cn_name, comic_author = get_comic_detail(book_name)
    print("name:", comic_cn_name)
    print("author:", comic_author)
    data = get_chapters(book_name)
    type_ = {}
    for i in data['build']['type']:
        print(i['name'])
        type_[i['name']] = i['id']
    data_type = input(f"please choose type: ")
    data = filter_list(data['groups']['default']['chapters'], lambda x: x['type'] == type_[data_type])
    for i in range(data.__len__()):
        print(i, data[i]['name'])
    print("if u want all chapters, please enter '-1'")
    chapters = input("please choose chapter(if you need multiple chapters, u can use ',' to split chapters):")
    if chapters == "-1":
        chapters = list(range(data.__len__()))
    else:
        chapters = chapters.split(",")
    print("downloading....")
    for i in chapters:
        img_list = get_chapter_images(data[int(i)]['id'])
        images_to_epub(img_list, f"{comic_cn_name}_{comic_author}_{data[int(i)]['name']}.epub", int(i),
                       data[int(i)]['name'], book_name, comic_author)
        print(f"chapter {data[int(i)]['name']} has been downloaded")
    shutil.rmtree("images")

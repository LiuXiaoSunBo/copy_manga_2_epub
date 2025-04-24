import json
import time
import shutil
import zipfile
from lxml import etree
import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from ebooklib import epub
from PIL import Image
import os
import random
key = b"xxxmanga.woo.key"
from bs4 import BeautifulSoup

proxies = {
    'http': 'http://127.0.0.1:7890',  # HTTP 代理
    'https': 'http://127.0.0.1:7890'  # HTTPS 代理
}


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
            response = requests.get("https://www.mangacopy.com/comic/" + comic_name, proxies=proxies).content
            soup = BeautifulSoup(response, 'html.parser')
            comic_data = soup.find_all(attrs={"class": "comicParticulars-right-txt"})
            return comic_data[0].text.strip(), comic_data[1].text.strip()
        except Exception as e:
            time.sleep(random.randint(2,4))


def get_chapters(comic_name):
    while True:
        try:
            response = requests.get(f"https://www.mangacopy.com/comicdetail/{comic_name}/chapters", proxies=proxies).json()
            return analyze_data(str(response['results']))
        except Exception as e:
            time.sleep(random.randint(2,4))


def get_chapter_images(chapter_id):
    while True:
        try:
            response = requests.get(f"https://www.mangacopy.com/comic/tianguodamojing/chapter/{chapter_id}", proxies=proxies).content
            data = analyze_data(
                BeautifulSoup(response, 'html.parser').find(name="div", attrs={"class": "imageData"}).attrs[
                    'contentkey'])
            return [i['url'] for i in data]
        except Exception as e:
            time.sleep(random.randint(2,4))


def filter_list(input_list, condition):
    return [item for item in input_list if condition(item)]
def fix_epub_ncx_manifest_order(epub_path, output_path=None):
    temp_dir = "temp_epub_fix"
    if output_path is None:
        output_path = epub_path.replace(".epub", "_fixed.epub")

    # Step 1: 解压 EPUB 到临时目录
    with zipfile.ZipFile(epub_path, 'r') as zip_ref:
        zip_ref.extractall(temp_dir)

    # Step 2: 找到 content.opf
    opf_path = None
    for root, dirs, files in os.walk(temp_dir):
        for file in files:
            if file.endswith(".opf"):
                opf_path = os.path.join(root, file)
                break
        if opf_path:
            break
    if not opf_path:
        raise FileNotFoundError("❌ 没找到 OPF 文件。")

    # Step 3: 解析 XML，找到 manifest
    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(opf_path, parser)
    root = tree.getroot()
    nsmap = root.nsmap
    default_ns = nsmap.get(None) or ''
    manifest = root.find(f".//{{{default_ns}}}manifest")

    # Step 4: 重排 manifest：将 id="ncx" 的项放最前
    items = list(manifest)
    ncx_item = None
    others = []
    for item in items:
        if item.get("id") == "ncx":
            ncx_item = item
        else:
            others.append(item)

    if ncx_item is not None:
        manifest[:] = []  # 清空 manifest 子元素
        manifest.append(ncx_item)
        for item in others:
            manifest.append(item)
        tree.write(opf_path, encoding="utf-8", xml_declaration=True, pretty_print=True)
        print("✅ 成功将 ncx 项移至 manifest 最前")
    else:
        print("⚠️ 没有找到 id='ncx' 的 manifest 项，跳过调整。")

    # Step 5: 重新打包为 EPUB
    with zipfile.ZipFile(output_path, 'w') as new_zip:
        # mimetype 必须无压缩写入
        mimetype_path = os.path.join(temp_dir, "mimetype")
        if os.path.exists(mimetype_path):
            new_zip.write(mimetype_path, "mimetype", compress_type=zipfile.ZIP_STORED)
        for folder, _, files in os.walk(temp_dir):
            for file in files:
                full_path = os.path.join(folder, file)
                rel_path = os.path.relpath(full_path, temp_dir)
                if rel_path == "mimetype":
                    continue
                new_zip.write(full_path, rel_path, compress_type=zipfile.ZIP_DEFLATED)

    shutil.rmtree(temp_dir)
    print(f"🎉 EPUB 已修复并保存到: {output_path}")


def images_to_epub(image_paths, output_file, id, title, book_name, author=""):
    path = f"images/{book_name}/{id}_{title}"
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
            print(f'{image_name} has been downloaded')
            time.sleep(random.randint(1, 2))
        else:
            print(f"download error: {url}")

    book = epub.EpubBook()
    book.set_identifier(str(id))
    book.set_title(title)
    book.set_language('en')
    book.add_author(author)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
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


    epub.write_epub(output_file, book)
    # 如果网盘阅读就加上这段安卓兼容性代码
    fix_epub_ncx_manifest_order(output_file)
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
    elif chapters.__contains__('~'):
        c_p = chapters.split("~")
        # 注意第二个值
        chapters = list(range(int(c_p[0]),int(c_p[1])+1))
    else:
        chapters = chapters.split(",")

    print(chapters)
    print("downloading....")
    for i in chapters:
        img_list = get_chapter_images(data[int(i)]['id'])
        images_to_epub(img_list, f"{comic_cn_name}_{comic_author}_{data[int(i)]['name']}.epub", int(i),
                       data[int(i)]['name'], book_name, comic_author)
        print(f"chapter {data[int(i)]['name']} has been downloaded")
    # shutil.rmtree("images")

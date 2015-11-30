#!/usr/bin/env python3

import codecs
from collections import namedtuple, OrderedDict
import datetime
from itertools import groupby
import os
import random

from bs4 import BeautifulSoup
from natsort import natsorted
import requests
import simplejson
from xdg import BaseDirectory

URL = 'http://www.mobilnisvet.com/mobilni-malioglasi'
STRING_INSIDE_AD_TABLE = (
    "Obavezno prvo pročitajte uputstvo za "
    "bezbednu kupoprodaju preko malih oglasa."
)
INDENT = " " * 4
DATA_FOLDER_NAME = 'mobilnisvet_ads'


AdInfo = namedtuple('AdInfo', [
    'title',
    'price',
    'new_price',
    'text',
    'contact_number',
    'date'
])


def _ad_info_json_object_hook(d):
    return namedtuple('AdInfo', d.keys())(*d.values())


def get_html_string(url):
    headers = [
        {"User-Agent": "Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.36"},
        {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2227.1 Safari/537.36"},
        {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.75.14 (KHTML, like Gecko) Version/7.0.3 Safari/7046A194A"},
        {"User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:31.0) Gecko/20130401 Firefox/31.0"},
        {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2227.0 Safari/537.36"}
    ]

    random_headers = random.choice(headers)

    r = requests.get(url, headers=random_headers)
    r.encoding = 'utf-8'
    html = r.text
    return html


def find_main_table(soup):
    def find_table_parent(e):
        return e if e.name == 'table' else find_table_parent(e.parent)
    e = soup(text=STRING_INSIDE_AD_TABLE)[0]
    return find_table_parent(e)


def get_ad_tables(main_table):
    return main_table.select("tr > td > table")


def parse_ad_table(ad_table):
    title_td, ad_td, contact_td = ad_table.select('tr > td')
    ad_title = ' '.join(title_td.stripped_strings)
    ad_price, ad_new_price, ad_text = ad_td.stripped_strings
    try:
        ad_contact_number, ad_date = contact_td.stripped_strings
    except ValueError:
        ad_date = next(contact_td.stripped_strings)
        ad_contact_number = "N/A"
    return AdInfo(
        title=ad_title, price=ad_price, new_price=ad_new_price,
        text=ad_text, contact_number=ad_contact_number, date=ad_date)


def get_ads(html):
    soup = BeautifulSoup(html, 'lxml')
    tables = get_ad_tables(find_main_table(soup))
    ad_infos = (parse_ad_table(t) for t in tables)
    return ad_infos


# Returns ad list with removed duplicates, sorted by title
def remove_duplicates(ads):
    def sort_group(l, attr):
        key_f = lambda x: getattr(x, attr)
        sorted_list = natsorted(l, key=key_f)
        return groupby(sorted_list, key_f)

    for _, title_group in sort_group(ads, 'title'):
        for _, price_group in sort_group(title_group, 'price'):
            for _, contact_group in sort_group(price_group, 'contact_number'):
                # Get newest ad if there are duplicates
                ad = sorted(
                    contact_group, reverse=True, key=lambda x: x.date
                )[0]
                yield ad


def get_default_filename():
    d = datetime.datetime.utcnow()
    filename = "ads-{time}.json".format(time=d.strftime("%Y-%m-%d--%H-%M-%S"))
    return filename


def write_data(data, filename=None, folder=None):
    if filename is None:
        filename = get_default_filename()
    if folder is None:
        folder = BaseDirectory.save_data_path(DATA_FOLDER_NAME)

    filepath = os.path.join(folder, filename)
    with codecs.open(filepath, 'w', encoding='utf-8') as f:
        simplejson.dump(data, f, ensure_ascii=False, indent=4)
    return filepath


def load_file(filepath):
    with codecs.open(filepath, 'r', encoding='utf-8') as f:
        data = simplejson.load(f, object_pairs_hook=OrderedDict)
        ads = [_ad_info_json_object_hook(e) for e in data]
        return ads


def get_previous_ads_file():
    folder = next(BaseDirectory.load_data_paths(DATA_FOLDER_NAME))
    files = sorted(os.listdir(folder), reverse=True)
    if len(files) == 0:
        return None

    newest_file = files[0]
    filepath = os.path.join(folder, newest_file)
    return filepath


def print_ads(ads):
    for ad in ads:
        print(INDENT, ad.title)
        print(INDENT, ad.price)
        print(INDENT, ad.text)
        print(INDENT, "{}  {}".format(ad.date, ad.contact_number))
        print()


def show_diff(all_old_ads, all_new_ads):
    old_ads = [x for x in all_old_ads if x not in all_new_ads]
    new_ads = [x for x in all_new_ads if x not in all_old_ads]
    print("OLD ADS:")
    print_ads(old_ads)
    print("\n\n")
    print("NEW ADS:")
    print_ads(new_ads)


def main():
    ads = get_ads(get_html_string(URL))
    all_new_ads = list(remove_duplicates(ads))

    previous_ads_file = get_previous_ads_file()
    if previous_ads_file is None:
        print("First run")
    else:
        all_old_ads = load_file(previous_ads_file)
        show_diff(all_old_ads, all_new_ads)

    write_data(all_new_ads)


if __name__ == '__main__':
    main()

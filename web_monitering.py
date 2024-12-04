import asyncio
import pandas as pd
from bs4 import BeautifulSoup
import geoip2.database
import socket
import pyap
import re
from urllib.parse import urlparse, urljoin
from playwright.async_api import async_playwright

db_path = 'GeoLite2-Country.mmdb'
contact_keywords = ['contact', 'support', 'help', 'about', 'Terms', 'Footer', 'Privacy']

def get_country_by_domain(domain):
    try:
        ip_address = socket.gethostbyname(domain)
        with geoip2.database.Reader(db_path) as reader:
            response = reader.country(ip_address)
            country = response.country.name
            return country
    except Exception as e:
        print(f"Domain is not correct {domain} with error {e}")
        return None

async def get_physical_address_and_email(page_url, page):
    async with async_playwright() as p:
        try:
            await page.goto(page_url, timeout=100000)
            visible_text = (await page.inner_text('body')).replace("\n", " ")            

            us_address = pyap.parse(visible_text, country='US')
            ca_address = pyap.parse(visible_text, country='CA')
            addresses = us_address + ca_address
            pattern = r'\d+[ \t][\w.,#-]+(?:[ \t][\w.,#-]+)*'
            text_address = [str(address) for address in list(addresses) if re.match(pattern, str(address))]
            emails = re.findall(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", visible_text)
            emails = [email.lower() for email in emails]
        except Exception as e:
            print(f"Error occurred while getting data: {e}")
            emails, text_address = '', ''

    return emails, text_address

async def get_internal_links(web_url, img_url, page):
    parsed_url = urlparse(web_url)
    country = get_country_by_domain(parsed_url.netloc)
    web_data = {}
    if country:
        web_data.update({'Web URL': web_url, 'Image URL': img_url, 'Country': country})

    base_url = parsed_url.scheme + "://" + parsed_url.netloc
    contact_pages = set()

    try:
        await page.goto(base_url, timeout=100000)
        anchor_tags = await page.query_selector_all("a[href]")
        for anchor in anchor_tags:
            href = await anchor.get_attribute("href")
            if href:
                full_url = urljoin(base_url, href)
                if any(keyword.lower() in full_url.lower() for keyword in contact_keywords):
                    contact_pages.add(full_url)
        
        internal_links = list(contact_pages)
        internal_links.append(base_url)

        if internal_links:
            print("Internal Links Found:")
            web_emails = []
            web_address = []
            for link in internal_links:
                print(link)
                emails, address = await get_physical_address_and_email(link, page)
                web_emails.extend(emails)
                web_address.extend(address) if address else None
            web_data.update({'Email': ", ".join(set(web_emails)), 'Address': ", ".join(set(web_address))})
        else:
            print(f"No Internal Links Found in {base_url}")

    except Exception as e:
        print(f"Error while processing {base_url}: {e}")

    return web_data

async def bolgging_or_forum(web_url, page):
    if any(keyword in web_url.lower() for keyword in ['blog', 'forum']):
        return True

async def web_checker(web_url=None, required_img_link=None):
    images_links = []
    image_not_found_website = None
    image_found_website = None
    down_website = None
    website_data = None
    try:
        async with async_playwright() as p:
            browser = await p.firefox.launch(headless=True)
            context = await browser.new_context(ignore_https_errors=True, locale="en-US")
            page = await context.new_page()
            response = await page.goto(web_url, timeout=100000)
            if response.status not in [400, 403, 404, 500, 503]:
                source_code = await page.content()


                if await bolgging_or_forum(web_url, page):
                    print(f"Blogging or Forum website {web_url}")
                    down_website = {"Web URL": web_url, "Image URL": required_img_link, "Result": "Blogging or Forum website"}
                else:
                    soup = BeautifulSoup(source_code, 'html.parser')

                    img_tags = soup.find_all('img')
                    a_tags = soup.find_all('a')
                    meta_tags = soup.find_all('meta')

                    web_base_url = urlparse(web_url).netloc
                    image_base_url = urlparse(required_img_link).netloc
                    if web_base_url in image_base_url:
                        response = await page.request.get(required_img_link, timeout=50000)
                        if response.status == 200:
                            print(f"Image Link found in website {web_url}")
                            image_found_website = {"Web URL": web_url, "Image URL": required_img_link, "Result": "Image Found"}
                            web_data = await get_internal_links(web_url, required_img_link, page)
                            if web_data:
                                website_data = web_data
                        else:
                            print(f"Image Link not found in website {web_url}")
                            image_not_found_website = {"Web URL": web_url, "Image URL": required_img_link, "Result": "Image Not Found"}
                    else:
                        parsed_url = urlparse(required_img_link)
                        relative_path = parsed_url.path.lstrip('/').replace("forum/", "")

                        for img_tag in img_tags:
                            img_src = img_tag.get('src')
                            if img_src:
                                images_links.append(img_src)

                        for a_tag in a_tags:
                            img_src = a_tag.get('href')
                            if img_src:
                                images_links.append(img_src)

                        for meta_tag in meta_tags:
                            img_src = meta_tag.get('content')
                            if img_src:
                                images_links.append(img_src)

                        image_found = False
                        for image_link in images_links:
                            if relative_path in image_link:
                                print(f"Image Link found in website {web_url}")
                                image_found_website = {"Web URL": web_url, "Image URL": required_img_link, "Result": "Image Found"}
                                web_data = await get_internal_links(web_url, required_img_link, page)
                                if web_data:
                                    website_data = web_data
                                image_found = True
                                break

                        if not image_found:
                            print(f"Image Link not found in website {web_url}")
                            image_not_found_website = {"Web URL": web_url, "Image URL": required_img_link, "Result": "Image Not Found"}

            else:
                print(f"Website not working {web_url} with Status code {response.status}")
                down_website = {"Web URL": web_url, "Image URL": required_img_link, "Result": f"Website not working with Status code {response.status}"}

            await browser.close()

    except Exception as error:
        print(f"Website not working {web_url} with error {str(error).strip()}")
        down_website = {"Web URL": web_url, "Image URL": required_img_link, "Result": str(error)}

    return image_not_found_website, image_found_website, down_website, website_data

async def web_moniter_by_file(req_file_path=None, task=None):
    websites_data = []
    image_not_found_websites = []
    image_found_websites = []
    down_websites = []

    file_extension = req_file_path.rsplit('.', 1)[1].lower()

    if file_extension == 'csv':
        input_df = pd.read_csv(req_file_path)
    elif file_extension == 'xlsx':
        input_df = pd.read_excel(req_file_path)
    else:
        print(f"Unsupported file type: {file_extension}")
        return
        
    input_df.columns = input_df.columns.str.lower()
    
    required_columns = {'image url', 'web url'}

    missing_columns = required_columns - set(input_df.columns)
    if missing_columns:
        print(f"Error: Missing required columns: {', '.join(missing_columns)}")
        return

    for _, row in input_df.iterrows():
        img_url = row['image url']
        web_url = row['web url'].strip('[]').strip('"')
        image_not_found_website, image_found_website, down_website, website_data = await web_checker(web_url=web_url, required_img_link=img_url)
        if image_not_found_website:
            image_not_found_websites.append(image_not_found_website)
        if image_found_website:
            image_found_websites.append(image_found_website)
        if down_website:
            down_websites.append(down_website)
        if website_data:
            websites_data.append(website_data)

    output_file = f"result/{task}_web_monitering_output.xlsx"
    website_data_df = pd.DataFrame(websites_data)
    img_not_found_df = pd.DataFrame(image_not_found_websites)
    img_found_df = pd.DataFrame(image_found_websites)
    down_web_df = pd.DataFrame(down_websites)    

    with pd.ExcelWriter(output_file) as writer:
        input_df.to_excel(writer, sheet_name='Input File', index=False)
        down_web_df.to_excel(writer, sheet_name='Websites Not Working', index=False)
        img_not_found_df.to_excel(writer, sheet_name='Image Not Found Websites', index=False)  
        img_found_df.to_excel(writer, sheet_name='Image Found Websites', index=False)
        website_data_df.to_excel(writer, sheet_name='Websites Data', index=False)

    print(f"Results saved to {output_file}")

async def web_moniter_by_urls(web_url=None, img_url=None, task=None):
    websites_data = []
    image_not_found_websites = []
    image_found_websites = []
    down_websites = []
    image_not_found_website, image_found_website, down_website, website_data = await web_checker(web_url=web_url, required_img_link=img_url)
    if image_not_found_website:
        image_not_found_websites.append(image_not_found_website)
    if image_found_website:
        image_found_websites.append(image_found_website)
    if down_website:
        down_websites.append(down_website)
    if website_data:
        websites_data.append(website_data)

    output_file = f"result/{task}_web_monitering_output.xlsx"
    input_df = pd.DataFrame([{'image url':img_url, 'web url':web_url}])
    website_data_df = pd.DataFrame(websites_data)
    img_not_found_df = pd.DataFrame(image_not_found_websites)
    img_found_df = pd.DataFrame(image_found_websites)
    down_web_df = pd.DataFrame(down_websites)    

    with pd.ExcelWriter(output_file) as writer:
        input_df.to_excel(writer, sheet_name='Input File', index=False)
        down_web_df.to_excel(writer, sheet_name='Websites Not Working', index=False)
        img_not_found_df.to_excel(writer, sheet_name='Image Not Found Websites', index=False)  
        img_found_df.to_excel(writer, sheet_name='Image Found Websites', index=False)
        website_data_df.to_excel(writer, sheet_name='Websites Data', index=False)

    print(f"Results saved to {output_file}")

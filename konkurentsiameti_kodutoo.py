from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import pandas as pd
import logging
import re
import matplotlib.pyplot as plt
import sys


logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')

CHROMEDRIVER_PATH = r"C:\Users\Markus\Desktop\chromedriver-win32\chromedriver.exe"
URL = "https://data.nordpoolgroup.com/auction/day-ahead/prices?deliveryDate=latest&currency=EUR&aggregation=DeliveryPeriod&deliveryAreas=EE"
MAX_WAIT_TIME = 10  # Max waittime to load the page (seconds)

def fetch_page_soup():
    """
    Initialize the Chrome webdriver, load the page and return parsed BeautifulSoup object.
    Returns None if loading or parsing fails.
    """
    service = Service(CHROMEDRIVER_PATH)
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # No visable window
    chrome_options.add_argument("--disable-gpu")

    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        driver.get(URL)
        wait = WebDriverWait(driver, MAX_WAIT_TIME)
        wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "tr.dx-row.dx-data-row")))
        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")
        return soup

    except (TimeoutException, WebDriverException) as e:
        logging.error(f"Failed to load page or find elements: {e}")
        return None

    finally:
        driver.quit()

def find_date(soup):
    """
    Extract the date string from the page soup.
    Returns the date string or None if not found.
    """
    date_box = soup.find("dx-date-box")

    if not date_box:
        logging.warning("Date box not found")
        return None

    hidden_input = date_box.find("input", {"type": "hidden"})

    if hidden_input and hidden_input.has_attr("value"):
        return hidden_input["value"]

    logging.warning("Hidden input with value not found inside date box")

    return None

def get_data_table(soup, date_text):
    """
    Extract the data rows from soup and return a pandas DataFrame with columns:
    'Date', 'Hour', 'Price (€/MWh)'.
    """
    rows = soup.select("tr.dx-row.dx-data-row.dx-column-lines, tr.dx-row.dx-data-row.dx-column-lines.dx-row-alt")
    data = []

    for tr in rows:
        tds = tr.find_all("td")
        if len(tds) >= 2:
            time_range = tds[0].get_text(strip=True)
            price_str = tds[1].get_text(strip=True).replace(",", ".")
            match = re.match(r"(\d{2}):\d{2}", time_range)
            hour = int(match.group(1)) if match else None

            try:
                price = float(price_str)
            except ValueError as e:
                logging.warning(f"Invalid price format '{price_str}' at hour {hour}: {e}")
                price = None

            data.append({
                "Date": date_text,
                "Hour": hour,
                "Price (€/MWh)": price
            })

    df = pd.DataFrame(data)
    df["SortKey"] = df["Hour"].apply(lambda x: 24 if x == 0 else x)
    df = df.sort_values(by="SortKey").drop(columns="SortKey").reset_index(drop=True)
    return df

def calculate_avg_price(df):
    """
    Calculate and return the average price from the DataFrame.
    """
    return df["Price (€/MWh)"].mean()

def plot_prices(df, avg_price, date_text):
    """
    Plot the hourly prices with a line indicating the average price.

    Parameters:
        df (DataFrame): DataFrame containing the price data.
        avg_price (float): The average price value to plot.
        date_text (str): Date string for the plot title.
    """
    df_plot = df.copy()
    df_plot["PlotHour"] = df_plot["Hour"].apply(lambda x: 24 if x == 0 else x)
    df_plot = df_plot.sort_values("PlotHour")

    plt.figure(figsize=(12, 6))
    plt.plot(df_plot["PlotHour"], df_plot["Price (€/MWh)"], marker='o')

    ticks = df_plot["PlotHour"]
    labels = [str(t) if t != 24 else '0' for t in ticks]

    plt.xticks(ticks, labels)
    plt.title(f"Hourly Electricity Prices: {date_text}")
    plt.xlabel("Hour (01:00–00:00)")
    plt.ylabel("Price (€/MWh)")
    plt.grid(True)

    # Add average price line and label
    plt.axhline(avg_price, color='red', linestyle='--', linewidth=1, label=f'Average Price: {avg_price:.2f} €/MWh')
    plt.legend()

    plt.show()

if __name__ == "__main__":
    soup = fetch_page_soup()
    if soup is None:
        logging.error("Failed to load or parse the webpage. Exiting.")
        sys.exit(1)

    date_text = find_date(soup)
    if not date_text:
        logging.error("Date not found. Exiting.")
        sys.exit(1)
    
    df = get_data_table(soup, date_text)
    avg_price = calculate_avg_price(df)

    print(f"Days average price: {avg_price:.2f} €/MWh")

    plot_prices(df, avg_price, date_text)

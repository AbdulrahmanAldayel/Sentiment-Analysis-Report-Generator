from bs4 import BeautifulSoup
from datetime import *
from copy import *
from random import *
from newscatcherapi import NewsCatcherApiClient
import requests
import openai

import os

# Load API keys from config
with open(os.path.join(os.path.dirname(__file__), '..', 'config', 'openai_apiKey.txt'), 'r') as f:
    openai.api_key = f.read().strip()

with open(os.path.join(os.path.dirname(__file__), '..', 'config', 'newscatcher_API_apiKey.txt'), 'r') as f:
    news_api_key = f.read().strip()

today = datetime.now().strftime("%x")
today_name = datetime.now().strftime("%m_%d_%Y")
total_PI = []

url = "https://api.newscatcherapi.com/v2/search"
querystring = {"q":"\"S-OIL\"","page":"1", "lang":'ko', 'page_size':'25'}
headers = {"x-api-key": news_api_key}
response = requests.request("GET", url, headers=headers, params=querystring)
soilheadline=response.json()
soilheadline = soilheadline['articles']
print(soilheadline)

with open(os.path.join(os.path.dirname(__file__), '..', 'templates', 'html_template.html'), encoding="utf8") as f:
    soup = BeautifulSoup(f, 'html.parser')

table = soup.select("#table")[0]


def _piGen(summ, title):
  prompt = f"Given the following title and summary of an article in Korean: Title: {title} Summary: {summ} could you gage on a scale of 0-10 how positively it mentions S-OIL company, with 0 being terrible publicity for S-OIL such as accusing it of mal-practice, and 10 being good coverage of S-OIL such as applauding S-OIL's initiatives, regardless of whether S-OIL is mentioned in the summary or not. I am asking you for a sentiment analysis of this article about S-OIL and assigning it to a score out of 10. Respond only with a single digit integer. Do not respond with anything else besides a number from 0 to 10. If not then just return a random number from 0-10."
  model = "text-davinci-003"
  response = openai.Completion.create(engine=model, prompt=prompt, max_tokens=50)
  pi = response.choices[0].text.strip()
  pi = ''.join(filter(str.isdigit, pi))[0]
  return pi

def _urlToHyperText(url):
  hyperText = soup.new_tag('a', href=url)
  hyperText.string = url
  return hyperText

def avgPI():
  return round((sum(total_PI) / len(total_PI)), 1)

def updatePI(PI):
  soup.find_all('td')[0].strong.string = f'Average PI: {str(PI)}'
  soup.find_all('table')[0]['style'] = f'background-color:{piColor(PI)}'
  return None

def piColor(pi):
  pi = float(pi)

  if pi >= 8:
    return '#32CD32' #LimeGreen
  elif pi >= 6:
    return '#FFA500' #Orange
  else:
    return '#FF4500' #OrangeRed

def addNum(article):
  no = soup.new_tag('p', style = 'margin-left: auto;margin-right: auto; margin-top: 10px; margin-bottom: 10px;font-family:Arial, sans-serif;font-size:14px;width: 50%')
  br = soup.new_tag('br')
  no.string = str(soilheadline.index(article)+1) + '.'
  soup.body.append(no)
  soup.append(br)
  return None

def createTable(table, article):
  new_table = copy(table)

  titleField = new_table.find_all('td')[0]
  PIField = new_table.find_all('td')[1]
  authorField = new_table.find_all('td')[2]
  agencyField = new_table.find_all('td')[3]
  pDateField = new_table.find_all('td')[4]
  summaryField = new_table.find_all('td')[5]
  urlField = new_table.find_all('td')[6]

  title = article['title']
  author = article['author']
  agency = article['clean_url']
  pDate = article['published_date'][0:10]
  summary = article['summary']

  if summary == '':
    return None

  pi = _piGen(summary, title)
  url = _urlToHyperText(article['link'])
  

  titleField.append(title)
  authorField.append(author)
  agencyField.append(agency)
  pDateField.append(pDate)
  summaryField.append(summary)
  urlField.append(url)
  PIField.strong.append(pi)

  PIField['style'] = f'background-color:{piColor(pi)}'

  total_PI.append(float(pi))

  return new_table

for article in soilheadline:
  newTable = createTable(table, article)
  if newTable is None:
    continue
  addNum(article)
  soup.body.append(newTable)
  

updatePI(avgPI())

table.decompose()

html = soup.prettify("utf-8")
with open(os.path.join(os.path.dirname(__file__), '..', 'output', f'S_OIL_PSR_{today_name}.html'), "wb") as file:
  file.write(html)




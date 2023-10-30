import requests 
import json
from bs4 import BeautifulSoup
import csv
import urllib.parse
import os

# Specify the directory and file paths
list_directory = "lists"
data_directory = "data"

# Create the directory if it doesn't exist
if not os.path.exists(list_directory):
    os.mkdir(list_directory)
    print(f"Directory '{list_directory}' created.")

# Create the directory if it doesn't exist
if not os.path.exists(data_directory):
    os.mkdir(data_directory)
    print(f"Directory '{data_directory}' created.")



# menu_maker.py
class Terminal_Menu:
    def __init__(self, menu_items: list):
        self.menu_items = menu_items

    def print_menu(self):
        for i, single_item in enumerate(self.menu_items, start=1):
            print(i, single_item)

    def select_menu_item(self):
        selection_prompt = "Select a number of an item (e.g. 1): "
        selection = input(selection_prompt)
        return self.menu_items[int(selection) - 1]

semester_file = "lists/semesters.txt"
program_list_file = 'lists/programs_list.json'
semesters = ''
programs = ''

def readSemesterFile(location):
	global semesters
	with open(location, "r") as file:
		semesters = file.read()
  
def readProgramsFile(location):
	global programs
	with open(location, 'r') as file:
		programs = json.load(file)

def getSemesterList():
	url = "https://registration.boun.edu.tr/BUIS/General/schedule.aspx?p=semester"
	r = requests.get(url)
	r.encoding = 'iso8859-9'

	return r.text

def scrapeSemesterList(htmlText):
	soup = BeautifulSoup(htmlText, 'lxml')

	semester_id = 'ctl00_cphMainContent_ddlSemester'
	semesters = soup.find('select', { 'id': semester_id })
	semesters = semesters.find_all('option')
	semester_list = []

	for s in semesters:
		semester_list.append(s.text)

	return semester_list

def writeSemesterList(semesters):
	with open(semester_file, mode='w', newline='') as file:
		for row in semesters:
			file.write(row+'\n')

def getProgramList():
	cookies = {
			'ASP.NET_SessionId': 'fdhnv2fpp35rdvvooyicppkt',
			'__utma': '151456186.97051176.1698659040.1698659040.1698659040.1',
			'__utmc': '151456186',
			'__utmz': '151456186.1698659040.1.1.utmcsr=(direct)|utmccn=(direct)|utmcmd=(none)',
			'__utmt': '1',
			'__utmb': '151456186.1.10.1698659040',
	}

	headers = {
			'Host': 'registration.boun.edu.tr',
			# 'Content-Length': '9163',
			'Cache-Control': 'max-age=0',
			'Sec-Ch-Ua': '"Not=A?Brand";v="99", "Chromium";v="118"',
			'Sec-Ch-Ua-Mobile': '?0',
			'Sec-Ch-Ua-Platform': '"macOS"',
			'Upgrade-Insecure-Requests': '1',
			'Origin': 'https://registration.boun.edu.tr',
			'Content-Type': 'application/x-www-form-urlencoded',
			'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.5993.88 Safari/537.36',
			'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
			'Sec-Fetch-Site': 'same-origin',
			'Sec-Fetch-Mode': 'navigate',
			'Sec-Fetch-User': '?1',
			'Sec-Fetch-Dest': 'document',
			'Referer': 'https://registration.boun.edu.tr/BUIS/General/schedule.aspx?p=semester',
			# 'Accept-Encoding': 'gzip, deflate, br',
			'Accept-Language': 'en-US,en;q=0.9',
			'Connection': 'close',
			# 'Cookie': 'ASP.NET_SessionId=fdhnv2fpp35rdvvooyicppkt; __utma=151456186.97051176.1698659040.1698659040.1698659040.1; __utmc=151456186; __utmz=151456186.1698659040.1.1.utmcsr=(direct)|utmccn=(direct)|utmcmd=(none); __utmt=1; __utmb=151456186.1.10.1698659040',
	}

	params = {
			'p': 'semester',
	}

	data = {
			'__VIEWSTATE': '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',
			'__VIEWSTATEGENERATOR': '4BE93B14',
			'__EVENTVALIDATION': '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',
			'ctl00$cphMainContent$ddlSemester': '2023/2024-1',
			'ctl00$cphMainContent$btnSearch': 'Go',
			'ctl00$cphMainContent$gRecResp': '03AFcWeA6g9ONNGc7p2KW9oc99_qE4qzLuW2KsSKUcF9EQ7cBZdRsBl--VdqychTism4wMeYRKPSiWVr6p984U59m3jvOxZfjSpwyZBeK4emRPlEEX-VEU5a6LnDhehAwNCEvS6suh8U2RKA0iJZzDZMhTTlAEaxnTnYoOzhblK_6S4ecH9C_IcMiOXArpb8218uS_HflP_8ASuhX2HvkAXZdzYfcN0_RgF3w_ifX62SjqddEMD3YJA17rL2Tnedz1NMLhOQquJK3fxyeybM1canEEK2rxUqF2zyhlkBe3LoanubAggRXz9VaiP9d_nNPl832-Rusf1_KIrmhBVTQQYzIhairO4Mw0lkq_cXwd4del_i9HyxNoL7G_fFgSSL4cMGuceeVSRR2W_rbKFuRtBj2FXb4OzXUGQvev4ea4HivXuleIbTk7qarB0I8ARYFUxrE424zvNTeweHqN1KBD0Uz5y8cRvdiQvNU2pUb6oZQfl1q4thANQNhGK6X-tZ5bHXO8VR6Fa1of2OZXPiYCwo-6lee1GezNsrU4cHWICZpSlLxqxdWRKvPZLgddT0dcPUInwQGpHknw',
	}

	response = requests.post(
			'https://registration.boun.edu.tr/BUIS/General/schedule.aspx',
			params=params,
			cookies=cookies,
			headers=headers,
			data=data,
			verify=False,
	)
	if("ECONOMICS" in response.text): return response.text
	else: raise Exception("GET PROGRAM LIST ERROR")

def scrapeProgramList(htmlText):
	soup = BeautifulSoup(htmlText, 'lxml')
	list_id = 'ctl00_cphMainContent_pnlCourseList'
	list = soup.find('table')

	program_list = {}
	for row in list.find_all('tr'):
		program_list[row.text.replace('\t', '').replace('\xa0', '').replace('\n','').rstrip().lstrip()] = row.find('a')['href']

	for program in program_list:
		d = program_list[program]
		program_list[program] = {}
		dd = d.split('?')[1].split('&')
		for e in dd:
			a = e.split('=')
			program_list[program][a[0]] = urllib.parse.unquote(urllib.parse.unquote_plus(a[1]))
		
	return program_list

def writeProgramList(programs):
	with open(program_list_file, 'w') as file:
		json.dump(programs, file, indent=4)  # Use indent for pretty formatting

# Gets schedule page of a program from registration
# Get params from the programs_list
# params = {
# 	"donem": "2023/2024-1",
# 	"kisaadi": "ASIA",
# 	"bolum": "ASIAN+STUDIES+WITH+THESIS"
# }
def getSchedule(params):
	print('Getting for '+params['kisaadi'])
	baseUrl = "https://registration.boun.edu.tr/scripts/sch.asp"

	r = requests.get(baseUrl, params=params)
	r.encoding = 'iso8859-9'

	return r.text

# Scrapes schedule page of a program to turn it into a list
def scrapeSchedule(htmlText):
	soup = BeautifulSoup(htmlText, 'lxml')

	table = soup.find_all('table')

	parsed_table = []
	for row in table[2].find_all('tr'):
		rowMatrix = []
		cells = row.find_all('td')
		for cell in cells:
			rowMatrix.append(cell.text.replace('\t', '').replace('\xa0', '').replace('\n',''))
		parsed_table.append(rowMatrix)

	return parsed_table

def writeCsv(name, parsed_table):
	print('Writing for '+name)
	with open('data/'+name+'.csv','w') as file:
		writer = csv.writer(file)
    # Write each row from the nested list
		for row in parsed_table:
			writer.writerow(row)

def parseDays(days):
	days_list: []
	for i in range(len(days)):
		if (days[i] == 'T'):
			try:
				if (days[i+1] == "h"):
					days_list.append('Th')
					i += 1
					continue
			except: 
				""""""
			days_list.append('T')
		days_list.append(days[i])
	return days_list

def parseHours(hours):
	return list(hours)

def parseRooms(rooms):
	rooms = rooms.split("|")
	rooms_list = []
	for r in rooms:
		rooms_list.append(r.rstrip().lstrip())
	return rooms_list

def makeObject(parsed_table):
	def getClass(i):
		if (parsed_table[i][0] == ''):
			return getClass(i-1)
		return parsed_table[i][0]
	for p in range(1, len(parsed_table)):
		row = parsed_table[p]
		code = getClass(p)
		credits = row[3]
		instr = row[6]
		days = parseDays(row[7])
		hours = parseHours(row[8])
		rooms = parseRooms(row[10])
		if (len(days) != len(hours)):
			print(f"{code} is broken")
			continue
		classHours = {}
		for index in range(len(days)):
			classHour = {
				"day": days[index],
				"hour": hours[index],
				"room": rooms[index]
			}
			classHours[index] = classHour

def getEverything():
	try:
		readSemesterFile(semester_file)
	except:
		semester_list = getSemesterList()
		scraped_semesters = scrapeSemesterList(semester_list)
		writeSemesterList(scraped_semesters)
		readSemesterFile(semester_file)

	try:
		readProgramsFile(program_list_file)
	except:
		programs_list = getProgramList()
		scraped_programs = scrapeProgramList(programs_list)
		writeProgramList(scraped_programs)
		readProgramsFile(program_list_file)

	global semesters
	global programs
	
	semesters = semesters.split('\n')
	for s in semesters:
		for p in programs:
			params = programs[p]
			params['donem'] = s
			a = scrapeSchedule(getSchedule(params))
			writeCsv(params['kisaadi'], a)

def menu():
	menu_items = [
		"GetAll",
	]
	menu = Terminal_Menu(menu_items)
	menu.print_menu()
	selection = menu.select_menu_item()
	if (selection == "GetAll"):
		getEverything()

if __name__ == "__main__":
    menu()

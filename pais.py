import requests
import csv

def fetch_countries_data():
    url = 'https://restcountries.com/v2/all?fields=name,demonym,flag'
    response = requests.get(url)
    response.raise_for_status()  # termina com erro se não for 200 OK
    return response.json()

def save_to_csv(countries, filename='countries_flags.csv'):
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['name', 'demonym', 'flag'])
        for c in countries:
            writer.writerow([
                c.get('name', ''),
                c.get('demonym', ''),
                c.get('flag', '')
            ])
    print(f'Arquivo salvo em: {filename}')

if __name__ == '__main__':
    countries = fetch_countries_data()
    save_to_csv(countries)

import requests
from bs4 import BeautifulSoup
import os
import re
import pandas as pd

# Define um cabeçalho User-Agent para as requisições
HEADERS = {
    'User-Agent': 'F1DriverImageScraper/1.3 (your-email@example.com) - Please replace with your actual email'
}


def baixar_foto_piloto(driver_id, wikipedia_url, pasta_destino="pilotos_fotos"):
    """
    Baixa a foto de perfil de um piloto de Fórmula 1 da Wikipédia (focado em en.wikipedia.org).

    Args:
        driver_id: O ID do piloto (para nomear o arquivo local).
        wikipedia_url (str): A URL completa da página da Wikipédia do piloto.
        pasta_destino (str): O nome da pasta onde as imagens serão salvas localmente.

    Returns:
        tuple: (URL web da imagem, Caminho local do arquivo baixado) ou (None, None) se falhar.
    """
    print(f"Acessando {wikipedia_url} para Driver ID: {driver_id}")

    try:
        response = requests.get(wikipedia_url, headers=HEADERS)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Erro ao acessar a página {wikipedia_url}: {e}")
        return None, None

    soup = BeautifulSoup(response.text, 'html.parser')

    img_candidate_url = None

    # Padrão para identificar claramente uma foto de perfil (ainda útil como filtro secundário)
    portrait_keywords_pattern = re.compile(r'(portrait|profile|headshot|driver_image)', re.IGNORECASE)

    # Padrão para excluir termos que NÃO são fotos de perfil de F1 ou são irrelevantes
    exclude_pattern = re.compile(
        r'(logo|flag|helmet|car|circuit|track|diagram|map|scheme|chassis|cockpit|engine|racecar|racing|event|champcar|indycar|kart|rally|moto|bike|motorcycle|gt_car|sportscar|team|badge|poster|trophy|pit_stop|track_layout|podium|start_grid|grid_position|pit_lane|racing_suit|overtake|accident|crash|helmet_vis|drawing|signature|illustration|signature_file)',
        re.IGNORECASE)

    # --- Nova Estratégia Principal: Buscar a "Foto do Card" pelo link mw-file-description ---
    infobox = soup.find('table', class_='infobox')
    if infobox:
        # A tag 'a' com class="mw-file-description" geralmente envolve a imagem principal do card/infobox
        main_image_link = infobox.find('a', class_='mw-file-description')

        if main_image_link:
            img_tag = main_image_link.find('img')
            if img_tag:
                src_attr = img_tag.get('src', '')
                alt_attr = img_tag.get('alt', '')
                width = int(img_tag.get('width', 0))

                # Última verificação contra termos de exclusão e tamanho mínimo
                if width > 100 and \
                        not exclude_pattern.search(src_attr) and not exclude_pattern.search(alt_attr):

                    file_page_href = main_image_link.get(
                        'href')  # Pega o link para a página do ficheiro (ex: /wiki/Ficheiro:...)
                    if file_page_href and file_page_href.startswith('/wiki/File:') or file_page_href.startswith(
                            '/wiki/Ficheiro:'):
                        file_page_url = f"https://en.wikipedia.org{file_page_href}"
                        print(
                            f"  [DEBUG] Candidato (foto do card) via mw-file-description. Verificando página do arquivo: {file_page_url}")
                        try:
                            file_page_response = requests.get(file_page_url, headers=HEADERS)
                            file_page_response.raise_for_status()
                            file_soup = BeautifulSoup(file_page_response.text, 'html.parser')

                            direct_link_element = file_soup.find('div', class_='fullImageLink')
                            if direct_link_element:
                                direct_link_a = direct_link_element.find('a')
                                if direct_link_a and direct_link_a.get('href'):
                                    img_candidate_url = direct_link_a.get('href')
                                    print(
                                        f"  [DEBUG] URL direta da imagem encontrada (foto do card): {img_candidate_url}")
                        except requests.exceptions.RequestException as e:
                            print(
                                f"  [DEBUG] Aviso: Erro ao acessar página do arquivo ({e}). Usando thumbnail se disponível.")

                    if not img_candidate_url and src_attr:
                        img_candidate_url = src_attr
                        print(f"  [DEBUG] Usando URL thumbnail da foto do card: {img_candidate_url}")

    # --- Fallback 1: Buscar a maior imagem relevante na infobox (se a estratégia do card falhar) ---
    if not img_candidate_url and infobox:
        largest_img_width = 0
        best_candidate_img_tag = None

        for img in infobox.find_all('img'):
            src_attr = img.get('src', '')
            alt_attr = img.get('alt', '')
            width = int(img.get('width', 0))

            # Condição para considerar uma imagem:
            # 1. Não é um thumbnail muito pequeno
            # 2. Não contém termos de exclusão no src ou alt
            # 3. Considera também o pattern de retrato, mas não é obrigatório para ser o "maior relevante"
            if width > 100 and \
                    not exclude_pattern.search(src_attr) and not exclude_pattern.search(alt_attr):

                if width > largest_img_width:
                    largest_img_width = width
                    best_candidate_img_tag = img

        if best_candidate_img_tag:
            img = best_candidate_img_tag
            src_attr = img.get('src', '')

            parent_a = img.find_parent('a')
            if parent_a and parent_a.get('href') and (
                    parent_a.get('href').startswith('/wiki/File:') or parent_a.get('href').startswith(
                    '/wiki/Ficheiro:')):
                file_page_url = f"https://en.wikipedia.org{parent_a.get('href')}"
                print(
                    f"  [DEBUG] Candidato principal (fallback 1) em infobox. Verificando página do arquivo: {file_page_url}")
                try:
                    file_page_response = requests.get(file_page_url, headers=HEADERS)
                    file_page_response.raise_for_status()
                    file_soup = BeautifulSoup(file_page_response.text, 'html.parser')
                    direct_link_element = file_soup.find('div', class_='fullImageLink')
                    if direct_link_element:
                        direct_link_a = direct_link_element.find('a')
                        if direct_link_a and direct_link_a.get('href'):
                            img_candidate_url = direct_link_a.get('href')
                            print(
                                f"  [DEBUG] URL direta da imagem encontrada (infobox, maior fallback): {img_candidate_url}")
                except requests.exceptions.RequestException as e:
                    print(f"  [DEBUG] Aviso: Erro ao acessar página do arquivo ({e}). Usando thumbnail se disponível.")

            if not img_candidate_url and src_attr:
                img_candidate_url = src_attr
                print(f"  [DEBUG] Usando URL thumbnail da infobox (maior fallback): {img_candidate_url}")

    # --- Fallback 2: Procurar a maior imagem relevante em toda a página (fora da infobox) ---
    if not img_candidate_url:
        largest_img_width = 0
        best_candidate_img_tag = None

        for img in soup.find_all('img'):
            src_attr = img.get('src', '')
            alt_attr = img.get('alt', '')
            width = int(img.get('width', 0))

            if width > 150 and \
                    not exclude_pattern.search(src_attr) and not exclude_pattern.search(alt_attr):
                if width > largest_img_width:
                    largest_img_width = width
                    best_candidate_img_tag = img

        if best_candidate_img_tag:
            img = best_candidate_img_tag
            src_attr = img.get('src', '')

            parent_a = img.find_parent('a')
            if parent_a and parent_a.get('href') and (
                    parent_a.get('href').startswith('/wiki/File:') or parent_a.get('href').startswith(
                    '/wiki/Ficheiro:')):
                file_page_url = f"https://en.wikipedia.org{parent_a.get('href')}"
                print(
                    f"  [DEBUG] Candidato principal (fallback 2) em página geral. Verificando página do arquivo: {file_page_url}")
                try:
                    file_page_response = requests.get(file_page_url, headers=HEADERS)
                    file_page_response.raise_for_status()
                    file_soup = BeautifulSoup(file_page_response.text, 'html.parser')
                    direct_link_element = file_soup.find('div', class_='fullImageLink')
                    if direct_link_element:
                        direct_link_a = direct_link_element.find('a')
                        if direct_link_a and direct_link_a.get('href'):
                            img_candidate_url = direct_link_a.get('href')
                            print(f"  [DEBUG] URL direta da imagem encontrada (geral, maior): {img_candidate_url}")
                except requests.exceptions.RequestException as e:
                    print(f"  [DEBUG] Aviso: Erro ao acessar página do arquivo ({e}). Usando thumbnail se disponível.")

            if not img_candidate_url and src_attr:
                img_candidate_url = src_attr
                print(f"  [DEBUG] Usando URL thumbnail da página geral (maior): {img_candidate_url}")

    if not img_candidate_url:
        print(f"Não foi possível encontrar uma URL de imagem válida para Driver ID: {driver_id}.")
        return None, None

    # Normaliza a URL da imagem
    final_img_url = img_candidate_url
    if final_img_url.startswith('//'):
        final_img_url = 'https:' + final_img_url
    elif final_img_url.startswith('/'):
        final_img_url = 'https://upload.wikimedia.org' + final_img_url

    # Prepara para baixar o arquivo localmente
    file_extension = ".jpg"  # Mais comum para fotos, mas pode ser png, svg
    if '.' in final_img_url.split('/')[-1]:
        ext = final_img_url.split('.')[-1]
        if '?' in ext:
            ext = ext.split('?')[0]
        file_extension = "." + ext

    nome_arquivo = f"{driver_id}{file_extension}"
    caminho_completo_arquivo = os.path.join(pasta_destino, nome_arquivo)

    os.makedirs(pasta_destino, exist_ok=True)

    print(f"Baixando imagem para: {caminho_completo_arquivo} da URL: {final_img_url}")
    try:
        img_response = requests.get(final_img_url, stream=True, headers=HEADERS)
        img_response.raise_for_status()

        with open(caminho_completo_arquivo, 'wb') as f:
            for chunk in img_response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"Foto para Driver ID {driver_id} baixada com sucesso!")
        return final_img_url, caminho_completo_arquivo
    except requests.exceptions.RequestException as e:
        print(f"Erro ao baixar a imagem de {wikipedia_url} para Driver ID {driver_id} ({final_img_url}): {e}")
        return None, None


# --- Configurações do Script Principal (para Pilotos) ---
input_csv_path = "drivers.csv"  # <--- ATUALIZE ESTE NOME DE ARQUIVO
output_images_folder = "pilotos_fotos"
output_csv_path = "pilotos_imagens_urls.csv"

if __name__ == "__main__":
    if not os.path.exists(input_csv_path):
        print(f"Erro: O arquivo CSV de entrada '{input_csv_path}' não foi encontrado.")
        print("Por favor, verifique o caminho e o nome do arquivo.")
    else:
        resultados_imagens = []

        try:
            df_drivers = pd.read_csv(input_csv_path)

            for index, row in df_drivers.iterrows():
                driver_id = row['driverId']
                wikipedia_url = row['url']

                web_image_url, local_image_path = baixar_foto_piloto(driver_id, wikipedia_url, output_images_folder)

                if web_image_url:
                    resultados_imagens.append({'driverId': driver_id, 'image_url': web_image_url})
                else:
                    resultados_imagens.append({'driverId': driver_id, 'image_url': 'N/A'})

            df_resultados = pd.DataFrame(resultados_imagens)
            df_resultados.to_csv(output_csv_path, index=False)
            print(f"\nCSV de URLs de imagens de pilotos salvo em: {output_csv_path}")
            print("Processo de download de fotos de pilotos concluído!")

        except KeyError as e:
            print(f"Erro: Coluna '{e}' não encontrada no seu CSV de entrada de pilotos.")
            print("Por favor, verifique se as colunas 'driverId' e 'url' existem no arquivo.")
        except Exception as e:
            print(f"Ocorreu um erro inesperado: {e}")
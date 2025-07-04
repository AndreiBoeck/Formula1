import requests
from bs4 import BeautifulSoup
import os
import re
import pandas as pd

# Define um cabeçalho User-Agent para as requisições
HEADERS = {
    'User-Agent': 'CircuitScraperBot/1.0 (andreicunhaboeck@gmail.com)'
    # É uma boa prática usar seu email para contato, caso necessário.
    # Ex: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    # Você pode usar um user-agent de navegador real se preferir, mas o Wikimedia pede um que identifique a ferramenta.
}


def baixar_desenho_pista(circuit_id, wikipedia_url, pasta_destino="circuitos_desenhos"):
    """
    Baixa o desenho do percurso de uma pista de Fórmula 1 da Wikipédia (focado em en.wikipedia.org).

    Args:
        circuit_id: O ID da pista (para nomear o arquivo local).
        wikipedia_url (str): A URL completa da página da Wikipédia.
        pasta_destino (str): O nome da pasta onde as imagens serão salvas localmente.

    Returns:
        tuple: (URL web da imagem, Caminho local do arquivo baixado) ou (None, None) se falhar.
    """
    print(f"Acessando {wikipedia_url} para Circuit ID: {circuit_id}")

    try:
        response = requests.get(wikipedia_url, headers=HEADERS)  # Adicionando User-Agent
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Erro ao acessar a página {wikipedia_url}: {e}")
        return None, None

    soup = BeautifulSoup(response.text, 'html.parser')

    img_candidate_url = None  # Esta será a URL web final da imagem a ser baixada

    # Padrão de regex para buscar termos relevantes em src/alt text (adicionado 'configurati' e 'track_map')
    circuit_pattern = re.compile(r'(circuit|track|layout|map|diagram|scheme|configurati|track_map)', re.IGNORECASE)
    # Padrão para excluir termos como 'logo', 'flag', 'photo', 'aerial'
    exclude_pattern = re.compile(r'(logo|flag|photo|aerial)', re.IGNORECASE)

    # --- Step 1: Prioridade Máxima - Buscar na Infobox por SVGs que sejam diagramas ---
    infobox = soup.find('table', class_='infobox')
    if infobox:
        for img in infobox.find_all('img'):
            src_attr = img.get('src', '')
            alt_attr = img.get('alt', '')

            # Prioriza SVGs e que contenham termos de circuito e NÃO contenham termos de exclusão
            if ('.svg' in src_attr.lower() and circuit_pattern.search(src_attr)) and \
                    not exclude_pattern.search(src_attr) and not exclude_pattern.search(alt_attr):

                if img.get('width') and int(img['width']) > 100:
                    parent_a = img.find_parent('a')
                    if parent_a and parent_a.get('href') and parent_a.get('href').startswith('/wiki/File:'):
                        file_page_url = f"https://en.wikipedia.org{parent_a.get('href')}"
                        print(
                            f"  [DEBUG] Candidato SVG em infobox com src/alt específico. Verificando página do arquivo: {file_page_url}")
                        try:
                            file_page_response = requests.get(file_page_url, headers=HEADERS)  # Adicionando User-Agent
                            file_page_response.raise_for_status()
                            file_soup = BeautifulSoup(file_page_response.text, 'html.parser')

                            direct_link_element = file_soup.find('div', class_='fullImageLink')
                            if direct_link_element:
                                direct_link_a = direct_link_element.find('a')
                                if direct_link_a and direct_link_a.get('href'):
                                    img_candidate_url = direct_link_a.get('href')
                                    print(
                                        f"  [DEBUG] URL direta da imagem SVG encontrada (infobox, src/alt): {img_candidate_url}")
                                    break
                        except requests.exceptions.RequestException as e:
                            print(
                                f"  [DEBUG] Aviso: Erro ao acessar página do arquivo ({e}). Usando thumbnail se disponível.")

                    if not img_candidate_url and src_attr:
                        img_candidate_url = src_attr
                        print(
                            f"  [DEBUG] Usando URL thumbnail da infobox (SVG, src/alt específico): {img_candidate_url}")
                        break

    # --- Step 2: Se não encontrou SVG, buscar outras imagens relevantes na infobox (PNG/JPG) ---
    if not img_candidate_url and infobox:
        for img in infobox.find_all('img'):
            src_attr = img.get('src', '')
            alt_attr = img.get('alt', '')

            # Busca imagens relevantes que NÃO sejam logos, flags, etc.
            if (circuit_pattern.search(src_attr) or circuit_pattern.search(alt_attr)) and \
                    not exclude_pattern.search(src_attr) and not exclude_pattern.search(alt_attr):

                if img.get('width') and int(img['width']) > 100:
                    parent_a = img.find_parent('a')
                    if parent_a and parent_a.get('href') and parent_a.get('href').startswith('/wiki/File:'):
                        file_page_url = f"https://en.wikipedia.org{parent_a.get('href')}"
                        print(f"  [DEBUG] Candidato PNG/JPG em infobox. Verificando página do arquivo: {file_page_url}")
                        try:
                            file_page_response = requests.get(file_page_url, headers=HEADERS)  # Adicionando User-Agent
                            file_page_response.raise_for_status()
                            file_soup = BeautifulSoup(file_page_response.text, 'html.parser')

                            direct_link_element = file_soup.find('div', class_='fullImageLink')
                            if direct_link_element:
                                direct_link_a = direct_link_element.find('a')
                                if direct_link_a and direct_link_a.get('href'):
                                    img_candidate_url = direct_link_a.get('href')
                                    print(
                                        f"  [DEBUG] URL direta da imagem PNG/JPG encontrada (infobox): {img_candidate_url}")
                                    break
                        except requests.exceptions.RequestException as e:
                            print(
                                f"  [DEBUG] Aviso: Erro ao acessar página do arquivo ({e}). Usando thumbnail se disponível.")

                    if not img_candidate_url and src_attr:
                        img_candidate_url = src_attr
                        print(f"  [DEBUG] Usando URL thumbnail da infobox (PNG/JPG): {img_candidate_url}")
                        break

    # --- Step 3: Último recurso na infobox - a maior imagem que NÃO é um logo, se for relevante ---
    if not img_candidate_url and infobox:
        largest_img_width = 0
        largest_img_src = None
        for img in infobox.find_all('img'):
            src_attr = img.get('src', '')
            alt_attr = img.get('alt', '')
            width = int(img.get('width', 0))

            # Considera apenas imagens grandes que não pareçam logos/flags/fotos
            if width > largest_img_width and \
                    not exclude_pattern.search(src_attr) and not exclude_pattern.search(alt_attr):
                largest_img_width = width
                largest_img_src = src_attr

        if largest_img_src and largest_img_width > 150:
            img_candidate_url = largest_img_src
            print(f"  [DEBUG] Usando a maior imagem relevante da infobox como fallback: {img_candidate_url}")

    # --- Step 4: Se ainda não encontrou, buscar por imagens relevantes em toda a página (amplo) ---
    if not img_candidate_url:
        for img in soup.find_all('img'):
            src_attr = img.get('src', '')
            alt_attr = img.get('alt', '')

            if (circuit_pattern.search(src_attr) or circuit_pattern.search(alt_attr)) and \
                    not exclude_pattern.search(src_attr) and not exclude_pattern.search(alt_attr):

                if img.get('width') and int(img['width']) > 200:  # Limiar maior para busca geral
                    parent_a = img.find_parent('a')
                    if parent_a and parent_a.get('href') and parent_a.get('href').startswith('/wiki/File:'):
                        file_page_url = f"https://en.wikipedia.org{parent_a.get('href')}"
                        print(
                            f"  [DEBUG] Candidato em página geral com src/alt. Verificando página do arquivo: {file_page_url}")
                        try:
                            file_page_response = requests.get(file_page_url, headers=HEADERS)  # Adicionando User-Agent
                            file_page_response.raise_for_status()
                            file_soup = BeautifulSoup(file_page_response.text, 'html.parser')
                            direct_link_element = file_soup.find('div', class_='fullImageLink')
                            if direct_link_element:
                                direct_link_a = direct_link_element.find('a')
                                if direct_link_a and direct_link_a.get('href'):
                                    img_candidate_url = direct_link_a.get('href')
                                    print(f"  [DEBUG] URL direta da imagem encontrada (geral): {img_candidate_url}")
                                    break
                        except requests.exceptions.RequestException as e:
                            print(
                                f"  [DEBUG] Aviso: Erro ao acessar página do arquivo ({e}). Usando thumbnail se disponível.")

                    if not img_candidate_url and src_attr:
                        img_candidate_url = src_attr
                        print(f"  [DEBUG] Usando URL thumbnail da página geral: {img_candidate_url}")
                        break

    if not img_candidate_url:
        print(f"Não foi possível encontrar uma URL de imagem válida para Circuit ID: {circuit_id}.")
        return None, None

    # Normaliza a URL da imagem (garante que comece com https://)
    final_img_url = img_candidate_url
    if final_img_url.startswith('//'):
        final_img_url = 'https:' + final_img_url
    elif final_img_url.startswith('/'):
        # Para caminhos relativos como /wikipedia/commons/... que precisam do domínio upload.wikimedia.org
        final_img_url = 'https://upload.wikimedia.org' + final_img_url

    # Prepara para baixar o arquivo localmente
    file_extension = ".png"
    if '.' in final_img_url.split('/')[-1]:
        ext = final_img_url.split('.')[-1]
        if '?' in ext:
            ext = ext.split('?')[0]
        file_extension = "." + ext

    nome_arquivo = f"{circuit_id}{file_extension}"
    caminho_completo_arquivo = os.path.join(pasta_destino, nome_arquivo)

    os.makedirs(pasta_destino, exist_ok=True)

    print(f"Baixando imagem para: {caminho_completo_arquivo} da URL: {final_img_url}")
    try:
        img_response = requests.get(final_img_url, stream=True, headers=HEADERS)  # Adicionando User-Agent
        img_response.raise_for_status()

        with open(caminho_completo_arquivo, 'wb') as f:
            for chunk in img_response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"Desenho para Circuit ID {circuit_id} baixado com sucesso!")
        return final_img_url, caminho_completo_arquivo
    except requests.exceptions.RequestException as e:
        print(f"Erro ao baixar a imagem de {wikipedia_url} para Circuit ID {circuit_id} ({final_img_url}): {e}")
        return None, None


# --- Configurações do Script Principal (sem alterações aqui) ---
input_csv_path = "circuits.csv"
output_images_folder = "circuitos_desenhos"
output_csv_path = "circuitos_imagens_urls.csv"

if __name__ == "__main__":
    if not os.path.exists(input_csv_path):
        print(f"Erro: O arquivo CSV de entrada '{input_csv_path}' não foi encontrado.")
        print("Por favor, verifique o caminho e o nome do arquivo.")
    else:
        resultados_imagens = []

        try:
            df_pistas = pd.read_csv(input_csv_path)

            for index, row in df_pistas.iterrows():
                circuit_id = row['circuitId']
                wikipedia_url = row['url']

                web_image_url, local_image_path = baixar_desenho_pista(circuit_id, wikipedia_url, output_images_folder)

                if web_image_url:
                    resultados_imagens.append({'circuitId': circuit_id, 'image_url': web_image_url})
                else:
                    resultados_imagens.append({'circuitId': circuit_id, 'image_url': 'N/A'})

            df_resultados = pd.DataFrame(resultados_imagens)
            df_resultados.to_csv(output_csv_path, index=False)
            print(f"\nCSV de URLs de imagens salvo em: {output_csv_path}")
            print("Processo concluído!")

        except KeyError as e:
            print(f"Erro: Coluna '{e}' não encontrada no seu CSV de entrada.")
            print("Por favor, verifique se as colunas 'circuitId' e 'url' existem no arquivo.")
        except Exception as e:
            print(f"Ocorreu um erro inesperado: {e}")
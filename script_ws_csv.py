from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.edge.service import Service
import csv
import time
from datetime import datetime
from datetime import timedelta

# Função para escapar campos CSV
def csv_escape(value):
    value = str(value)  # Converte para string para evitar erros com floats
    if isinstance(value, str) and (',' in value or '"' in value or '\n' in value):
        return '"{}"'.format(value.replace('"', '""'))
    return value

# Função para normalizar valores monetários
def parse_amount(amount_str):
    cleaned = amount_str.replace("−", "-").replace("$", "").replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return amount_str

# Função para formatar datas
def parse_date(date_str):
    if "Today" in date_str:
        return datetime.now().strftime("%Y-%m-%d")
    elif "Yesterday" in date_str:
        return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    try:
        return datetime.strptime(date_str, "%B %d, %Y").strftime("%Y-%m-%d")
    except:
        return date_str

# Configuração do Microsoft Edge WebDriver
edge_options = webdriver.EdgeOptions()
edge_options.add_argument("--start-maximized")
# Especifique o caminho do msedgedriver.exe se necessário
# service = Service("C:/WebDriver/msedgedriver.exe")
# driver = webdriver.Edge(service=service, options=edge_options)
driver = webdriver.Edge(options=edge_options)  # Use se msedgedriver.exe está no PATH

try:
    # Passo 1: Navegar até a página de login
    driver.get("https://my.wealthsimple.com/app/login")
    print("Navegou para a página de login. Faça login manualmente.")
    input("Pressione Enter após navegar manualmente para a página de transações do cartão de crédito...")

    # Passo 2: Verificar se a página de transações carregou
    wait = WebDriverWait(driver, 30)
    print("Aguardando carregamento da página de transações...")
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    
    try:
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Transaction') or contains(text(), 'Recent Activity')]")))
        print("Página de transações detectada.")
    except:
        print("AVISO: Não foi encontrado um elemento indicando transações. Verifique se está na página correta.")

    # Passo 3: Rolar até o final da página
    print("Rolando a página para carregar todas as transações...")
    last_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height
    print("Rolagem concluída.")

    # Passo 4: Extrair transações por data
    rows = []
    dates = driver.find_elements(By.TAG_NAME, "h2")
    print(f"Encontradas {len(dates)} datas.")

    for date_el in dates:
        date = parse_date(date_el.text.strip())
        
        # Encontrar o div seguinte à h2 (grupo de transações) e extrair buttons dentro
        try:
            group_div = date_el.find_element(By.XPATH, "following-sibling::div[1]")
            transaction_buttons = group_div.find_elements(By.TAG_NAME, "button")
            print(f"Para data '{date}': Encontrados {len(transaction_buttons)} botões de transações.")
        except:
            continue

        for button in transaction_buttons:
            # Sub-elementos (p, span, div)
            sub_elements = button.find_elements(By.XPATH, ".//*[self::p or self::span or self::div]")
            
            description = None
            trans_type = None
            account = None
            amount = None
            status = None
            
            for sub in sub_elements:
                text = sub.text.strip()
                if not description and text and not "$" in text and not any(word in text.lower() for word in ["purchase", "refund", "credit card"]):
                    description = text
                elif "Purchase" in text or "Refund" in text:
                    trans_type = text
                elif "Credit card" in text:
                    account = text
                elif "$" in text and any(char.isdigit() for char in text):
                    amount = text.replace("−", "-")
                elif text.lower() == "pending":
                    status = text

            if date and description and amount:
                rows.append([date, description, trans_type or "", account or "", parse_amount(amount), status or ""])
                print(f"Transação encontrada: {date}, {description}, {amount}")

    if not rows:
        print("AVISO: Nenhuma transação encontrada. Verifique o HTML ou a página de transações.")

    # Passo 5: Remover duplicatas
    unique_rows = [list(t) for t in set(tuple(row) for row in rows)]
    print(f"Total de transações únicas: {len(unique_rows)}")

    # Passo 6: Salvar CSV
    csv_header = ["Date", "Description", "Type", "Account", "Amount", "Status"]
    csv_rows = [csv_header] + unique_rows
    with open("transactions.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for row in csv_rows:
            writer.writerow([csv_escape(cell) for cell in row])

    print("Arquivo CSV gerado com sucesso: transactions.csv")

except Exception as e:
    print(f"Erro durante a execução: {e}")
    print("Dicas de depuração:")
    print("- Verifique se está na página correta de transações após o login.")
    print("- Inspecione o HTML (F12) para confirmar as tags (h2 para datas, button para transações, p para descrições/amounts).")
    print("- Certifique-se de que o Edge WebDriver está atualizado e no PATH.")
    print("- Teste com uma conexão de internet estável.")

finally:
    driver.quit()
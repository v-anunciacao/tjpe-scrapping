import os
import sys
import re
import json
import time
import base64
import logging
import traceback
import subprocess
import requests
import urllib3
import speech_recognition as sr
from dotenv import load_dotenv

load_dotenv()

TOKEN_TELEGRAM = os.getenv("TOKEN_TELEGRAM", "")
ID_CHAT_TELEGRAM = os.getenv("ID_CHAT_TELEGRAM", "")
NPU_PROCESSO = os.getenv("NPU_PROCESSO", "")
DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))
CAMINHO_JSON = os.path.join(DIRETORIO_ATUAL, f"processo_{NPU_PROCESSO}.json")
CAMINHO_WAV = os.path.join(DIRETORIO_ATUAL, f"captcha_temporario_{os.getpid()}.wav")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def mapear_palavras_para_caracteres(texto):
    mapa = {
        "zero": "0", "zéro": "0", "um": "1", "uma": "1", "hum": "1", "dois": "2", "duas": "2",
        "três": "3", "tres": "3", "trez": "3", "quatro": "4", "quarto": "4", "cinco": "5",
        "seis": "6", "meia": "6", "meia-dúzia": "6", "sete": "7", "set": "7",
        "oito": "8", "nove": "9", "dez": "10",
        "a": "a", "á": "a", "aa": "a", "b": "b", "bê": "b", "be": "b",
        "c": "c", "cê": "c", "ce": "c", "d": "d", "dê": "d", "de": "d",
        "e": "e", "é": "e", "f": "f", "efe": "f", "g": "g", "gê": "g", "ge": "g",
        "h": "h", "agá": "h", "aga": "h", "i": "i", "í": "i",
        "j": "j", "jota": "j", "k": "k", "cá": "k", "ka": "k",
        "l": "l", "ele": "l", "m": "m", "eme": "m", "em": "m",
        "n": "n", "ene": "n", "o": "o", "ó": "o", "p": "p", "pê": "p", "pe": "p",
        "q": "q", "quê": "q", "que": "q", "r": "r", "erre": "r",
        "s": "s", "esse": "s", "t": "t", "tê": "t", "te": "t", "u": "u",
        "v": "v", "vê": "v", "ve": "v", "w": "w", "dáblio": "w", "dábliu": "w", "dabliu": "w",
        "x": "x", "xis": "x", "y": "y", "ípsilon": "y", "ipsilon": "y",
        "z": "z", "zê": "z", "ze": "z"
    }
    texto = str(texto or "").lower().strip()
    texto = texto.replace("-", " ")
    palavras = texto.split()
    resultado = ""
    for palavra in palavras:
        resultado += mapa.get(palavra, palavra)
    return re.sub(r"[^a-z0-9]", "", resultado.lower())

def emitir_notificacao_windows(titulo, mensagem):
    if not sys.platform.startswith("win"):
        logging.info("Notificação Windows ignorada: sistema não é Windows.")
        return
    msg_escapada = str(mensagem).replace("'", "''")
    titulo_escapado = str(titulo).replace("'", "''")
    comando = f"(New-Object -ComObject Wscript.Shell).Popup('{msg_escapada}', 15, '{titulo_escapado}', 64)"
    subprocess.Popen(["powershell", "-NoProfile", "-Command", comando])

def enviar_telegram(mensagem):
    if not TOKEN_TELEGRAM:
        logging.warning("TOKEN_TELEGRAM não configurado. Envio Telegram ignorado.")
        return
    url = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendMessage"
    payload = {"chat_id": ID_CHAT_TELEGRAM, "text": mensagem, "parse_mode": "Markdown"}
    try:
        resposta = requests.post(url, json=payload, timeout=20)
        logging.info(f"Notificação Telegram enviada: {resposta.status_code}")
        if resposta.status_code != 200:
            logging.warning(f"Resposta Telegram: {resposta.text[:500]}")
    except Exception as e:
        logging.error(f"Erro ao enviar Telegram: {e}")

def obter_primeiro_registro(dados):
    if isinstance(dados, list) and dados:
        return dados[0]
    if isinstance(dados, dict):
        return dados
    return {}

def escapar_markdown(texto):
    valor = str(texto if texto is not None else "")
    for caractere in ["\\", "_", "*", "[", "]", "`"]:
        valor = valor.replace(caractere, f"\\{caractere}")
    return valor

def chave_movimentacao(m):
    return f"{m.get('dataHora', '')}|{m.get('fase', '')}|{m.get('texto', '')}|{m.get('complemento', '')}"

def obter_resumo_novidades(antigo, novo):
    if antigo is None:
        return "Primeiro monitoramento iniciado para este processo."
    
    mudancas = []
    try:
        a, n = obter_primeiro_registro(antigo), obter_primeiro_registro(novo)
        
        def formatar_movimentacoes():
            mov_a = a.get("movimentacoes", [])
            mov_n = n.get("movimentacoes", [])
            chaves_antigas = {chave_movimentacao(m) for m in mov_a}
            novos = [m for m in mov_n if chave_movimentacao(m) not in chaves_antigas]
            for m in novos:
                data = m.get('dataHora', 'S/D')[:10]
                fase = m.get('fase', 'N/A')
                texto = m.get('texto', '') or m.get('complemento', '') or ''
                desc = f"\n_{escapar_markdown(texto.strip())}_" if texto.strip() else ""
                mudancas.append(f"📍 *Nova Movimentação ({escapar_markdown(data)})*\n{escapar_markdown(fase)}{desc}")

        def formatar_partes():
            partes_a = {p.get('nome') for p in a.get('partes', [])}
            partes_n = [p for p in n.get('partes', []) if p.get('nome') not in partes_a]
            for p in partes_n:
                mudancas.append(f"👤 *Nova Parte*: {escapar_markdown(p.get('nome'))} ({escapar_markdown(p.get('tipo', 'N/A'))})")

        def formatar_assuntos():
            assuntos_a = set(a.get('assuntos', []))
            assuntos_n = [asst for asst in n.get('assuntos', []) if asst not in assuntos_a]
            for asst in assuntos_n:
                mudancas.append(f"📚 *Novo Assunto*: {escapar_markdown(asst)}")

        formatar_movimentacoes()
        formatar_partes()
        formatar_assuntos()
        
        chaves_pulo = ["movimentacoes", "partes", "assuntos", "historico", "dataAtualizacao"]
        alterados = [k for k in n if k not in chaves_pulo and a.get(k) != n.get(k)]
        for k in alterados:
            mudancas.append(f"⚙️ *{escapar_markdown(k.capitalize())}*: {escapar_markdown(a.get(k))} ➔ {escapar_markdown(n.get(k))}")
                    
    except Exception as e:
        logging.error(f"Erro ao processar novidades: {e}")
        
    return "\n\n".join(mudancas) if mudancas else "Alterações internas detectadas."

def carregar_dados_antigos():
    try:
        with open(CAMINHO_JSON, "r", encoding="utf-8") as arquivo:
            return json.load(arquivo)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as e:
        caminho_backup = f"{CAMINHO_JSON}.corrompido.{int(time.time())}.bak"
        logging.error(f"Arquivo JSON anterior inválido ou corrompido: {e}")
        try:
            os.replace(CAMINHO_JSON, caminho_backup)
            logging.error(f"Backup do JSON corrompido criado em: {caminho_backup}")
        except Exception as erro_backup:
            logging.error(f"Não foi possível criar backup do JSON corrompido: {erro_backup}")
        return None

def salvar_json_atomico(dados):
    caminho_temporario = f"{CAMINHO_JSON}.tmp"
    with open(caminho_temporario, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=4)
    os.replace(caminho_temporario, CAMINHO_JSON)
    logging.info(f"Arquivo JSON atualizado de forma atômica: {CAMINHO_JSON}")

def verificar_e_atualizar_dados(dados_novos):
    dados_antigos = carregar_dados_antigos()

    def realizar_atualizacao():
        novidades = obter_resumo_novidades(dados_antigos, dados_novos)
        salvar_json_atomico(dados_novos)
        
        mensagem = f"🔔 *Atualização no Processo {NPU_PROCESSO}*\n\n{novidades}"
        emitir_notificacao_windows("TJPE: Atualização Detectada", f"Novidades no processo {NPU_PROCESSO}")
        enviar_telegram(mensagem)
        logging.info(f"Dados atualizados com sucesso. Novidades: {novidades}")

    realizar_atualizacao() if dados_novos != dados_antigos else logging.info("Sem alterações no processo.")

def processar_resposta_consulta(resposta):
    def tratar_sucesso():
        logging.info("Consulta retornou status 200. Tentando interpretar JSON.")
        try:
            dados = resposta.json()
        except Exception as e:
            logging.error(f"Consulta retornou 200, mas o corpo não é JSON válido: {e}")
            logging.error(f"Corpo da resposta: {resposta.text[:1000]}")
            return False
        logging.info("Consulta bem-sucedida.")
        verificar_e_atualizar_dados(dados)
        return True

    def tratar_falha():
        logging.warning(f"Falha na consulta: {resposta.status_code}. Possível CAPTCHA inválido, expirado ou sessão incompatível.")
        logging.warning(f"Corpo da resposta: {resposta.text[:500]}")
        return False

    return tratar_sucesso() if resposta.status_code == 200 else tratar_falha()

def validar_configuracoes():
    if not re.fullmatch(r"\d{20}", NPU_PROCESSO):
        raise ValueError(f"NPU_PROCESSO inválido: {NPU_PROCESSO}")
    if not ID_CHAT_TELEGRAM:
        logging.warning("ID_CHAT_TELEGRAM não configurado.")
    if not TOKEN_TELEGRAM:
        logging.warning("TOKEN_TELEGRAM não configurado. Telegram será ignorado.")

def resolver_captcha_e_consultar():
    validar_configuracoes()
    url_captcha = "https://srv01.tjpe.jus.br/consultaprocessualunificadaservico/api/captcha"
    url_processo = "https://srv01.tjpe.jus.br/consultaprocessualunificadaservico/api/processo"
    
    cabecalhos = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Accept': 'application/json, text/plain, */*',
        'Content-Type': 'application/json;charset=utf-8'
    }
    
    urllib3.disable_warnings()
    reconhecedor = sr.Recognizer()
    
    for tentativa in range(1, 51):
        sessao = requests.Session()
        sessao.verify = False
        
        try:
            logging.info(f"Tentativa {tentativa}")
            resposta_captcha = sessao.get(url_captcha, headers=cabecalhos, timeout=20)
            
            if resposta_captcha.status_code != 200:
                logging.warning(f"Falha ao obter CAPTCHA: {resposta_captcha.status_code}. Corpo: {resposta_captcha.text[:500]}")
                continue
                
            dados = resposta_captcha.json()
            audio = dados.get("audio", "")
            if not audio:
                logging.warning(f"Captcha sem campo de áudio na tentativa {tentativa}. Payload: {dados}")
                continue
            audio_b64 = audio.split(",", 1)[1] if "," in audio else audio
            try:
                audio_bytes = base64.b64decode(audio_b64, validate=True)
            except Exception as e:
                logging.warning(f"Base64 do áudio inválido na tentativa {tentativa}: {e}")
                continue
            
            try:
                with open(CAMINHO_WAV, "wb") as f:
                    f.write(audio_bytes)
                
                with sr.AudioFile(CAMINHO_WAV) as fonte:
                    audio_gravado = reconhecedor.record(fonte)
                    
                try:
                    dict_rec = reconhecedor.recognize_google(audio_gravado, language="pt-BR", show_all=True)
                except sr.UnknownValueError:
                    logging.warning(f"Reconhecimento não entendeu o áudio na tentativa {tentativa}.")
                    continue
                except sr.RequestError as e:
                    logging.warning(f"Serviço de reconhecimento indisponível na tentativa {tentativa}: {e}")
                    continue
            finally:
                try:
                    if os.path.exists(CAMINHO_WAV):
                        os.remove(CAMINHO_WAV)
                except Exception as e:
                    logging.warning(f"Não foi possível remover o WAV temporário: {e}")

            if not dict_rec or "alternative" not in dict_rec:
                logging.warning(f"Nenhuma alternativa retornada na tentativa {tentativa}.")
                continue

            textos = []
            for alternativa in dict_rec.get("alternative", []):
                transcricao = alternativa.get("transcript", "")
                confianca = alternativa.get("confidence", 0)
                texto_mapeado = mapear_palavras_para_caracteres(transcricao)
                texto_mapeado = re.sub(r"[^a-zA-Z0-9]", "", texto_mapeado).lower()
                textos.append({"texto": texto_mapeado, "transcricao": transcricao, "confianca": confianca})

            textos_validos = [item for item in textos if len(item["texto"]) == 5 and re.fullmatch(r"[a-z0-9]{5}", item["texto"])]
            textos_validos = sorted(textos_validos, key=lambda item: item.get("confianca", 0), reverse=True)

            if not textos_validos:
                logging.warning(f"Nenhum CAPTCHA válido extraído. Alternativas brutas: {textos}")
                continue

            texto_final = textos_validos[0]["texto"]
            logging.info(f"Captcha candidato: {texto_final} | transcrição: {textos_validos[0]['transcricao']} | confiança: {textos_validos[0].get('confianca', 0)}")
            
            cabecalhos_post = cabecalhos.copy()
            cabecalhos_post['captcha'] = texto_final
            
            resposta_processo = sessao.post(url_processo, headers=cabecalhos_post, json={"npu": NPU_PROCESSO}, timeout=20)
            
            if processar_resposta_consulta(resposta_processo):
                return
                
        except Exception as e:
            logging.error(f"Erro na tentativa {tentativa}: {e}")
            logging.error(f"DEBUG - Configurações: token_configurado={bool(TOKEN_TELEGRAM)}, npu={NPU_PROCESSO}, caminho_json={CAMINHO_JSON}")
            logging.error(traceback.format_exc())
        
        time.sleep(min(1 + tentativa * 0.25, 8))
            
    logging.error("Excedido limite de tentativas.")

if __name__ == "__main__":
    resolver_captcha_e_consultar()


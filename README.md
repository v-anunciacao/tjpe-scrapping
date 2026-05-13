# TJPE Scrapping

Este projeto contém um scraper autônomo e resiliente para consulta processual no Tribunal de Justiça de Pernambuco (TJPE). O script resolve automaticamente o CAPTCHA de áudio do sistema e monitora o andamento de um processo, notificando via Telegram e pop-up do Windows caso haja novas movimentações, partes ou assuntos no processo.

## Principais Features

- **Resolução Automática de CAPTCHA de Áudio**: Utiliza o Google Speech Recognition (`speech_recognition`) para baixar e interpretar o áudio do CAPTCHA.
- **Mapeamento Fonético Avançado**: Possui um dicionário extensivo para corrigir interpretações erradas de reconhecimento de fala (ex: "zéro" para "0", "ípsilon" para "y", "cá" para "k").
- **Validação e Ranking de Confiança**: Filtra transcrições garantindo o formato exato de 5 caracteres alfanuméricos (`[a-z0-9]{5}`) e ordena as alternativas pela pontuação de confiança da API do Google, melhorando muito a taxa de sucesso.
- **Sistema de Retentativas com Backoff**: Implementa um loop robusto de até 50 tentativas, com incremento progressivo no tempo de espera (backoff) entre as requisições para respeitar os limites do servidor.
- **Comparação Inteligente de Dados (Diffing)**: Não depende apenas do tamanho da lista de movimentações. O sistema cria chaves compostas (data, fase, texto, complemento) para identificar de forma atômica o que há de novo, cobrindo também novas partes e novos assuntos no processo.
- **Segurança de Dados**: O arquivo histórico JSON é salvo de maneira atômica (usando arquivo temporário `.tmp` e `os.replace`), prevenindo corrupção por queda de energia ou interrupção. Também gera backups automáticos caso encontre arquivos corrompidos.
- **Notificações Multicanal**:
  - **Telegram**: Mensagens ricas e formatadas (sem perder suporte a caracteres especiais devido a uma função de `escape` nativa) com emojis sinalizando o tipo de atualização.
  - **Pop-up Windows**: Em ambientes Windows, utiliza COM objects do Wscript para exibir um aviso visual persistente.
- **Código Limpo, Defensivo e Configurável**: Gerenciamento de segredos via variáveis de ambiente (`.env`), validações rigorosas de payload Base64, e controle de fluxo com timeouts para evitar threads travadas.

## Requisitos

- Python 3.x
- Pacotes listados (ou requeridos pelo script): `requests`, `SpeechRecognition`, `python-dotenv`

## Como Usar

1. Clone o repositório.
2. Crie um arquivo `.env` baseado no `.env.example` fornecido, preenchendo seu token do Telegram, Chat ID e o NPU do processo alvo.
3. Execute o script:
   ```bash
   python tjpe-scrapping.py
   ```

## Boas Práticas Adotadas

- **Gestão de Recursos**: Deleção forçada e segura do arquivo `.wav` temporário utilizando blocos `try/finally`, evitando acúmulo de lixo mesmo após exceptions de reconhecimento.
- **Segurança da Informação**: Nenhum token hardcoded no repositório.
- **Isolamento de Processos**: Nomes de arquivos temporários utilizam o PID da execução `os.getpid()` para permitir execuções em paralelo.

## Observação

Este código destina-se a fins de estudo e facilitação pessoal na automação de consultas públicas disponibilizadas pelo respectivo tribunal.

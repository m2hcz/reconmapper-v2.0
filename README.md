# ReconMapper v2.0

**Um crawler web assíncrono e inteligente para reconhecimento em segurança ofensiva, construído com Python, Playwright e asyncio.**

---

<p align="center">
  <img src="https://raw.githubusercontent.com/M4cs/recon-mapper/main/assets/logo.png" width="350"/>
</p>

<p align="center">
  <a href="https://github.com/M4cs/recon-mapper/stargazers"><img src="https://img.shields.io/github/stars/M4cs/recon-mapper?style=social" alt="Stars"></a>
  <a href="https://github.com/M4cs/recon-mapper/issues"><img src="https://img.shields.io/github/issues/M4cs/recon-mapper" alt="Issues"></a>
  <a href="https://github.com/M4cs/recon-mapper/blob/main/LICENSE"><img src="https://img.shields.io/github/license/M4cs/recon-mapper" alt="License"></a>
</p>

## 📌 Sobre o Projeto

O **ReconMapper** é uma ferramenta de reconhecimento (recon) projetada para automatizar a fase inicial de um pentest ou de uma análise de segurança ofensiva. Em vez de depender de requisições simples, ele utiliza um **navegador headless controlado pelo Playwright** para renderizar páginas web dinâmicas, incluindo aplicações de página única (SPAs) construídas com frameworks como React, Angular ou Vue.js.

Isso permite uma descoberta de endpoints, subdomínios e arquivos muito mais profunda e realista, simulando a interação de um usuário real e extraindo links que crawlers tradicionais não conseguiriam encontrar. O uso de **`asyncio`** e múltiplos workers garante uma performance excepcional, mesmo ao lidar com alvos grandes e complexos.

## ✨ Principais Funcionalidades

* **Renderização Completa de JavaScript:** Usa um navegador Chromium real (via Playwright) para garantir que todo o conteúdo dinâmico seja processado.
* **Crawling Assíncrono e Paralelo:** Utiliza `asyncio` e múltiplos workers para escanear dezenas de páginas simultaneamente com alta velocidade.
* **Extração Inteligente de Links:** Encontra URLs em tags HTML (`<a>`, `<script>`, etc.), e também dentro de código JavaScript e strings usando expressões regulares.
* **Controle de Escopo Automático:** Mantém o foco no domínio alvo e em seus subdomínios, evitando o rastreamento de links de terceiros.
* **Respeito ao `robots.txt`:** Processa e obedece às regras definidas no arquivo `robots.txt` do alvo para um crawling mais ético.
* **Normalização de URLs:** Limpa e padroniza as URLs encontradas para evitar a duplicação de trabalho e garantir a consistência dos dados.
* **Saída Estruturada:** Gera os resultados em tempo real (streaming) como objetos JSON e pode criar um relatório final consolidado com todos os achados.
* **Flexibilidade:** Permite configurar o número de threads, a profundidade do rastreamento, timeouts e o modo de execução do navegador (com ou sem interface gráfica).

---

## 🚀 Instalação e Uso

### Pré-requisitos

* Python 3.8+
* Pip

### Exemplos de Uso

* **Varredura básica em um alvo:**
    ```sh
    python recon_mapper.py -t example.com
    ```

* **Varredura com mais threads e salvando um resumo final:**
    ```sh
    python recon_mapper.py -t example.com -T 20 --summary resultados.json
    ```

* **Varredura em modo "verbose" e com interface gráfica (não headless) para depuração:**
    ```sh
    python recon_mapper.py -t example.com -v --no-headless
    ```

* **Salvando todos os eventos encontrados em tempo real (streaming):**
    ```sh
    python recon_mapper.py -t example.com -o eventos.jsonl
    ```

### Opções da Linha de Comando

| Argumento | Atalho | Descrição | Padrão |
| :--- | :--- | :--- | :--- |
| `--target` | `-t` | **(Obrigatório)** O domínio alvo, sem 'https://'. | N/A |
| `--threads` | `-T` | Número de workers paralelos para o crawling. | 10 |
| `--timeout` | | Timeout em segundos para cada requisição. | 15 |
| `--max-depth` | | Profundidade máxima de rastreamento a partir da URL inicial. | 5 |
| `--headless` | | Executar o navegador em modo headless (sem interface). Use `--no-headless` para visualizar a interface. | True |
| `--out` | `-o` | Arquivo de saída para eventos JSON (um por linha, streaming). | None |
| `--summary` | | Arquivo JSON de saída com o resumo final de todos os achados. | None |
| `--verbose` | `-v` | Ativa logs detalhados e imprime os eventos JSON na tela em tempo real. | False |

---

## 🗺️ Roadmap do Projeto

* [ ] Implementar detecção de tecnologias e CMS.
* [ ] Adicionar um módulo para tirar screenshots das páginas visitadas.
* [ ] Integrar com APIs externas para enriquecimento de dados (ex: Shodan, VirusTotal).
* [ ] Melhorar a extração de informações sensíveis (chaves de API, segredos) do código-fonte.

---

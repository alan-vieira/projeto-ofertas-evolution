# 🛒 Projeto Ofertas Evolution

Sistema automatizado de scraping e envio de ofertas de produtos para grupos do WhatsApp, integrado com a Evolution API.

## 📋 Descrição

Este projeto é uma solução completa para captura, processamento e envio de ofertas de produtos de grandes marketplaces brasileiros (Magalu, Mercado Livre, Shopee e Amazon) diretamente para grupos do WhatsApp, utilizando a Evolution API como gateway de mensagens.

## ✨ Funcionalidades

- 🔍 **Scrapers especializados** para múltiplos marketplaces:
  - Magazine Luiza (Magalu)
  - Mercado Livre
  - Shopee
- 📊 **Parsers inteligentes** para Amazon e Shopee
- 📸 **Processamento automático de imagens** das ofertas
- 💬 **Envio automatizado** para grupos do WhatsApp via Evolution API
- ⚡ **Cache com Redis** para melhor performance
- 💾 **Persistência de dados** com PostgreSQL
- 🔄 **Formatação automática** de posts com layout profissional
- 🎯 **Sistema de configuração flexível** via arquivos JSON

## 🛠️ Tecnologias Utilizadas

- **Python 3.x** - Linguagem principal
- **Playwright** - Automação de navegador web
- **Redis** - Sistema de cache
- **PostgreSQL** - Banco de dados
- **Docker & Docker Compose** - Containerização
- **Evolution API** - Gateway para WhatsApp

## 📦 Pré-requisitos

Antes de começar, você precisará ter instalado:

- Python 3.8 ou superior
- Docker e Docker Compose
- Git
- Uma instância da Evolution API configurada

## 🚀 Instalação

### 1. Clone o repositório

```bash
git clone https://github.com/alan-vieira/projeto-ofertas-evolution.git
cd projeto-ofertas-evolution
```

### 2. Crie um ambiente virtual

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

### 4. Configure as variáveis de ambiente

Copie o arquivo de exemplo e edite com suas configurações:

```bash
cp .env.example .env
```

Edite o arquivo `.env` com suas credenciais:

```env
EVOLUTION_API_URL=http://localhost:8080
EVOLUTION_API_KEY=sua_api_key_aqui
WHATSAPP_GROUP_JID=seu_jid_aqui
REDIS_HOST=localhost
REDIS_PORT=6379
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=seu_usuario
POSTGRES_PASSWORD=sua_senha
POSTGRES_DB=evolution_db
```

### 5. Configure o settings.json

Copie o arquivo de exemplo e edite com suas configurações:

```bash
cp config/settings.json.example config/settings.json
```

## 🐳 Executando com Docker

A maneira mais fácil de executar o projeto é usando Docker Compose:

```bash
docker-compose up -d
```

Isso iniciará todos os serviços necessários:
- Aplicação principal
- Redis (cache)
- PostgreSQL (banco de dados)

Para ver os logs:

```bash
docker-compose logs -f
```

Para parar os serviços:

```bash
docker-compose down
```

## 💻 Uso

### Executar o scraper principal

```bash
python main.py
```

### Enviar ofertas manualmente

```bash
python send_only.py
```

## 📁 Estrutura do Projeto

```
projeto-ofertas-evolution/
├── config/
│   ├── settings.json          # Configurações sensíveis (não versionado)
│   └── settings.json.example  # Modelo de configurações
├── src/
│   ├── core/
│   │   ├── config_loader.py   # Carregamento de configurações
│   │   ├── formatter.py       # Formatação de posts
│   │   ├── models.py          # Modelos de dados
│   │   └── utils.py           # Utilitários gerais
│   ├── extractors/
│   │   ├── magalu.py          # Scraper do Magalu
│   │   └── mercadolivre.py    # Scraper do Mercado Livre
│   ├── parsers/
│   │   ├── amazon_parser.py   # Parser da Amazon
│   │   └── shopee_parser.py   # Parser da Shopee
│   ├── cache.py               # Gerenciamento de cache
│   ├── evolution_sender.py    # Envio via Evolution API
│   ├── image_processor.py     # Processamento de imagens
│   └── post_generator.py      # Geração de posts
├── .env.example               # Modelo de variáveis de ambiente
├── .gitignore
├── docker-compose.yaml        # Configuração Docker
├── main.py                    # Ponto de entrada principal
├── requirements.txt           # Dependências Python
└── send_only.py               # Script de envio manual
```

## 🔒 Segurança

⚠️ **IMPORTANTE:**

- Nunca commite o arquivo `config/settings.json` ou `.env` com dados reais
- Use sempre os arquivos `.example` como modelo
- Mantenha suas API keys e senhas em segurança
- Rotacione suas credenciais periodicamente

## 📊 Fluxo de Funcionamento

1. **Extração**: Os scrapers capturam dados dos marketplaces
2. **Parsing**: Os parsers processam e estruturam as informações
3. **Cache**: Dados são armazenados em cache Redis para performance
4. **Processamento**: Imagens são otimizadas e posts são formatados
5. **Envio**: Ofertas são enviadas para grupos do WhatsApp via Evolution API

## 🤝 Contribuindo

Contribuições são bem-vindas! Sinta-se à vontade para:

1. Fazer um fork do projeto
2. Criar uma branch para sua feature (`git checkout -b feature/MinhaFeature`)
3. Commit suas mudanças (`git commit -m 'Adiciona nova feature'`)
4. Push para a branch (`git push origin feature/MinhaFeature`)
5. Abrir um Pull Request

## 📝 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

## 👨‍💻 Autor

**Alan Silva Vieira**

- GitHub: [@alan-vieira](https://github.com/alan-vieira)
- LinkedIn: [Alan Silva Vieira](https://www.linkedin.com/in/alan-silva-vieira/)

## 🙏 Agradecimentos

- [Evolution API](https://github.com/EvolutionAPI/evolution-api) - Pelo excelente gateway de mensagens
- Comunidade Python e de automação
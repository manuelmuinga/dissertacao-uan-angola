-- ============================================================
-- Data Warehouse: AmeacasAngola_DW
-- SQL Server Express (Windows 11 — instalado localmente)
-- Dissertacao UAN — Manuel Muinga 2026
-- ============================================================
-- PREREQUISITOS:
--   1. SQL Server Express: https://www.microsoft.com/pt-pt/sql-server/sql-server-downloads
--   2. SSMS: https://aka.ms/ssmsfullsetup
--   3. Abrir SSMS -> ligar a localhost\SQLEXPRESS
--   4. Executar este script (F5)
-- ============================================================

USE master;
GO
IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'AmeacasAngola_DW')
    CREATE DATABASE AmeacasAngola_DW;
GO
USE AmeacasAngola_DW;
GO

-- Dimensao Tempo
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'dim_tempo')
CREATE TABLE dim_tempo (
    id_tempo    INT IDENTITY(1,1) PRIMARY KEY,
    data        DATE NOT NULL,
    ano         INT, mes INT, dia INT, hora INT,
    dia_semana  NVARCHAR(20), trimestre INT, semana_ano INT
);

-- Dimensao Categoria
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'dim_categoria')
CREATE TABLE dim_categoria (
    id_categoria INT IDENTITY(1,1) PRIMARY KEY,
    categoria    NVARCHAR(50) NOT NULL UNIQUE,
    nivel_risco  NVARCHAR(20)
);

-- Dimensao Plataforma OSINT
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'dim_plataforma')
CREATE TABLE dim_plataforma (
    id_plataforma    INT IDENTITY(1,1) PRIMARY KEY,
    plataforma       NVARCHAR(50) NOT NULL UNIQUE,
    tipo             NVARCHAR(50),
    ferramenta_osint NVARCHAR(100),
    custo            NVARCHAR(20) DEFAULT '0 USD'
);

-- Dimensao Provincia (18 provincias angolanas)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'dim_provincia')
CREATE TABLE dim_provincia (
    id_provincia INT IDENTITY(1,1) PRIMARY KEY,
    provincia    NVARCHAR(100) NOT NULL UNIQUE,
    regiao       NVARCHAR(50),
    latitude     FLOAT,
    longitude    FLOAT
);

-- Tabela de Factos (central do modelo estrela)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'factos_ameacas')
CREATE TABLE factos_ameacas (
    id_facto           BIGINT IDENTITY(1,1) PRIMARY KEY,
    id_categoria       INT REFERENCES dim_categoria(id_categoria),
    id_plataforma      INT REFERENCES dim_plataforma(id_plataforma),
    id_provincia       INT REFERENCES dim_provincia(id_provincia),
    id_tempo           INT REFERENCES dim_tempo(id_tempo),
    id_externo         NVARCHAR(255) NOT NULL UNIQUE,
    id_anonimizado     NVARCHAR(32),
    texto_resumo       NVARCHAR(200),
    categoria          NVARCHAR(50),
    confianca          FLOAT,
    alerta_emitido     BIT DEFAULT 0,
    plataforma         NVARCHAR(50),
    provincia          NVARCHAR(100),
    data_publicacao    NVARCHAR(50),
    data_classificacao DATETIME DEFAULT GETDATE(),
    modelo_ia          NVARCHAR(50) DEFAULT 'BERT-BERTimbau',
    segundos_detecao   INT,
    horas_antecedencia INT
);
GO

-- Indices para Power BI
CREATE INDEX idx_cat   ON factos_ameacas(categoria);
CREATE INDEX idx_plat  ON factos_ameacas(plataforma);
CREATE INDEX idx_prov  ON factos_ameacas(provincia);
CREATE INDEX idx_data  ON factos_ameacas(data_classificacao);
CREATE INDEX idx_alert ON factos_ameacas(alerta_emitido);
GO

-- Dados iniciais
INSERT INTO dim_categoria VALUES ('Normal','BAIXO'),('Desinformacao','ALTO'),('Discurso de Odio','ALTO'),('Mobilizacao Hostil','ALTO');
INSERT INTO dim_plataforma VALUES ('facebook','REDE_SOCIAL','Playwright + Chromium','0 USD'),('twitter','REDE_SOCIAL','Playwright + Nitter','0 USD'),('telegram','MENSAGENS','t.me/s/ scraper','0 USD'),('youtube','VIDEO','yt-dlp','0 USD'),('web_angop','WEB','aiohttp + BeautifulSoup','0 USD'),('web_verangola','WEB','aiohttp + BeautifulSoup','0 USD'),('web_rna','WEB','aiohttp + BeautifulSoup','0 USD'),('web_expansao','WEB','aiohttp + BeautifulSoup','0 USD');
INSERT INTO dim_provincia VALUES ('Luanda','NORTE',-8.84,13.23),('Benguela','CENTRO',-12.58,13.40),('Huambo','CENTRO',-12.77,15.73),('Bie','CENTRO',-12.35,17.33),('Malanje','NORTE',-9.54,16.34),('Huila','SUL',-14.93,13.50),('Cabinda','NORTE',-5.55,12.19),('Cunene','SUL',-16.65,15.47),('Namibe','SUL',-15.19,12.15),('Zaire','NORTE',-6.27,14.24),('Uige','NORTE',-7.61,15.06),('Kwanza Norte','NORTE',-9.28,14.78),('Kwanza Sul','CENTRO',-10.85,14.25),('Lunda Norte','LESTE',-8.66,19.92),('Lunda Sul','LESTE',-10.26,20.42),('Moxico','LESTE',-11.87,19.92),('Cuando Cubango','SUL',-14.67,19.91),('Bengo','NORTE',-9.10,13.73);
GO

-- Vista unificada para Power BI
CREATE OR ALTER VIEW vw_ameacas_completo AS
SELECT f.id_facto, f.id_anonimizado, f.texto_resumo,
       f.categoria, f.confianca, f.alerta_emitido,
       f.plataforma, f.provincia, f.data_publicacao,
       f.data_classificacao, f.modelo_ia,
       f.segundos_detecao, f.horas_antecedencia,
       c.nivel_risco, p.tipo AS tipo_plataforma,
       p.ferramenta_osint, pv.regiao, pv.latitude, pv.longitude,
       t.ano, t.mes, t.dia, t.hora, t.dia_semana, t.trimestre
FROM factos_ameacas f
LEFT JOIN dim_categoria  c  ON f.id_categoria  = c.id_categoria
LEFT JOIN dim_plataforma p  ON f.id_plataforma = p.id_plataforma
LEFT JOIN dim_provincia  pv ON f.id_provincia  = pv.id_provincia
LEFT JOIN dim_tempo      t  ON f.id_tempo      = t.id_tempo;
GO

PRINT 'AmeacasAngola_DW criado. Ligar Power BI: localhost\SQLEXPRESS -> AmeacasAngola_DW -> vw_ameacas_completo';

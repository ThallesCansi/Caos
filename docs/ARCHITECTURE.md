# Arquitetura do projeto

## 1. Separação de responsabilidades

A arquitetura evita transformar notebooks em scripts monolíticos.

### `src/amazon_chaos/io`
Acesso às fontes externas. Deve fazer o mínimo de transformação possível e registrar o que foi pedido/recebido.

### `src/amazon_chaos/preprocess`
Transformações determinísticas: unidades, coordenadas, agregações temporais, clipping, QC e harmonização.

### `src/amazon_chaos/features`
Variáveis derivadas com significado científico: VPD, anomalias, métricas de perturbação, gradientes.

### `src/amazon_chaos/nonlinear`
Algoritmos de dinâmica não linear e controles. Não deve conhecer APIs de dados.

### `apps/`
Exploração, visualização, seleção de parâmetros e narrativa. Não é a fonte única da lógica científica; funções reutilizáveis ficam em `src/`.

### `configs/`
Cada experimento relevante deve ser reproduzível a partir de configuração versionada.

### `metadata/`
Catálogo, manifestos, checksums, datas de acesso, parâmetros de origem e proveniência.

## 2. Camadas de dados

- `raw`: bytes originais recebidos das fontes. Imutável.
- `external`: camadas auxiliares externas não tratadas.
- `interim`: dados convertidos/recortados, ainda próximos da fonte.
- `processed`: tabelas/cubos prontos para análise.
- `cache`: resultados descartáveis que podem ser reconstruídos.

Nunca sobrescrever `raw`. Se a fonte atualizar, salvar uma nova versão/pasta e atualizar o manifesto.

## 3. Unidade espacial

A candidata inicial é a **célula da grade ERA5**. Camadas de 30 m e vetoriais são agregadas à célula climática, produzindo atributos como fração florestal, área desmatada e pressão por fogo.

Essa decisão ainda é experimental. Antes de congelá-la, comparar pelo menos:

1. célula ERA5 pura;
2. janela espacial ao redor do centro da célula;
3. regiões/estratos ecológicos maiores, se a escala de reanálise exigir.

## 4. Unidade temporal

A série dinâmica principal começa em resolução horária. Produtos anuais (MapBiomas/PRODES) não são interpolados para “virar séries horárias”; eles caracterizam o **estado/gradiente de perturbação** ou definem janelas antes/depois.

## 5. Side effects

Downloads e escrita de grandes arquivos são comandos explícitos de CLI. Apps marimo leem dados já existentes. Esse desenho impede que uma alteração reativa em um widget dispare downloads caros.

## 6. Proveniência mínima por arquivo

Registrar:

- fonte e dataset;
- URL/endpoint lógico;
- data/hora de acesso UTC;
- parâmetros da requisição;
- período e área;
- variáveis;
- tamanho;
- SHA-256;
- commit/configuração que produziu derivados.

## 7. Escala HPC

Quando o piloto for validado, a mesma biblioteca `src/` deve rodar localmente ou no ambiente de alto desempenho. Apps marimo não devem ser pré-requisito para processamento batch.

# Audio to Text (Tkinter + faster-whisper)

Aplicativo desktop simples que grava áudio do microfone no macOS e transcreve em texto usando o modelo Whisper via **faster-whisper**. Ideal para rascunhar ideias faladas, registrar reuniões curtas ou fazer anotações rápidas em português com termos técnicos em inglês.

```mermaid
flowchart TD
    A[Usuário clica em Start Recording] --> B[Captura com sounddevice]
    B --> C[Buffer de áudio em memória]
    C --> D[Thread de transcrição]
    D --> E[faster-whisper (modelo base por padrão)]
    E --> F[Texto formatado em PT-BR]
    F --> G[Exibição no Tkinter + botão Copy Text]
```

## Recursos
- Janela única em Tkinter, com botão para iniciar/parar a gravação.
- Indicador de tempo durante a captura de áudio.
- Transcrição local em PT-BR usando Whisper (`faster-whisper`) com preservação de termos técnicos em inglês.
- Área de texto com botão de copiar para a área de transferência.
- Modelo carregado sob demanda (lazy-load) para reduzir o tempo de inicialização.

## Pré-requisitos
- macOS com Python 3.11+ (testado em 3.12).
- Acesso ao microfone (o sistema solicitará permissão na primeira execução).
- Xcode Command Line Tools instaladas (`xcode-select --install`) para compilar dependências, se necessário.

## Instalação

```bash
git clone https://github.com/<seu-usuario>/audio-to-text.git
cd audio-to-text

python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install faster-whisper sounddevice numpy
```

> Observação: na primeira execução de `faster-whisper`, o modelo (`base` por padrão) será baixado automaticamente (~140 MB).

## Uso

```bash
source .venv/bin/activate
python transcriber_app.py
```

1. Clique em **Start Recording** para começar a gravar; o status exibirá o tempo em segundos.
2. Fale normalmente em português. Use termos técnicos em inglês quando necessário.
3. Clique em **Stop Recording** para transcrever; o texto aparecerá na área principal.
4. Use **Copy Text** para enviar o resultado direto para a área de transferência.

## Ajustando o modelo

Para maior precisão (com custo de desempenho), altere a linha em `transcriber_app.py` dentro de `_get_model()`:

```python
self.model = WhisperModel(
    "small",  # opções: base, small, medium, large-v2
    device="cpu",
    compute_type="int8",  # int8_float16 ou float16 se preferir mais fidelidade
)
```

- `base`: leve (padrão). Boa velocidade e tamanho.
- `small`: mais preciso, recomendado para PT+EN híbrido.
- `medium`/`large-v2`: máxima fidelidade, porém lentos e exigem bastante RAM.

## Resolução de problemas

- **Erro de acesso ao microfone**: confirme que o Python tem permissão em Preferências do Sistema → Segurança e privacidade → Microfone.
- **Latência alta**: troque para um modelo menor (`base`) ou mantenha a janela aberta para reutilizar o modelo já carregado.
- **Termos em inglês saem traduzidos**: ajuste o `initial_prompt` em `transcriber_app.py` para incluir exemplos do seu domínio.

## Contribuição

Contribuições e melhorias são bem-vindas! Abra uma issue ou envie um pull request com ajustes (por exemplo, suporte a hotkeys, histórico de transcrições ou integração com serviços externos).

## Licença

Defina a licença desejada (por exemplo, MIT) antes de tornar o repositório público.

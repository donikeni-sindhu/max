"""Cached Attention Is All You Need path used when live steps fail in DEMO_MODE."""

from app.models import DEMO_USER_ID

PAPER_TITLE = "Attention Is All You Need"
PAPER_ABS = "https://arxiv.org/abs/1706.03762"
PAPER_PDF = "https://arxiv.org/pdf/1706.03762"
DEMO_GOAL = "I want to understand the paper 'Attention Is All You Need'"

PAPER_EXCERPT = (
    "The paper replaces recurrent sequence models with a Transformer built from stacked "
    "encoder and decoder blocks. It depends on sequence-to-sequence learning, encoder-decoder "
    "models, word embeddings, attention, self-attention, multi-head attention, and positional encoding."
)

CONCEPTS: list[dict[str, object]] = [
    {
        "name": "Sequence-to-Sequence",
        "level": 1,
        "order_index": 1,
        "status": "active",
        "explanation": "A model that reads a whole input sequence, then writes an output sequence one piece at a time.",
    },
    {
        "name": "Encoder-Decoder",
        "level": 1,
        "order_index": 2,
        "status": "pending",
        "explanation": "The encoder turns the input into a representation. The decoder turns that representation into the output.",
    },
    {
        "name": "Word Embeddings",
        "level": 1,
        "order_index": 3,
        "status": "pending",
        "explanation": "Each word is stored as a list of numbers so similar words sit near each other.",
    },
    {
        "name": "Attention",
        "level": 2,
        "order_index": 4,
        "status": "pending",
        "explanation": "The model looks back at the input positions that matter for the word it is writing now.",
    },
    {
        "name": "Self-Attention",
        "level": 2,
        "order_index": 5,
        "status": "pending",
        "explanation": "Each word looks at the other words in the same sentence and keeps the relevant ones.",
    },
    {
        "name": "Transformer Architecture",
        "level": 3,
        "order_index": 6,
        "status": "pending",
        "explanation": "A stack of encoder and decoder blocks that use attention instead of recurrence.",
    },
    {
        "name": "Multi-Head Attention + Positional Encoding",
        "level": 3,
        "order_index": 7,
        "status": "pending",
        "explanation": "Several attention heads look for different relationships. Positional encoding adds word order.",
    },
]

RESOURCES: list[dict[str, object]] = [
    {
        "concept_name": "Sequence-to-Sequence",
        "title": "Sequence to Sequence Learning with Neural Networks",
        "url": "https://arxiv.org/abs/1409.3215",
        "source": "arxiv",
        "score": 0.90,
        "selected": True,
    },
    {
        "concept_name": "Word Embeddings",
        "title": "The Illustrated Word2vec",
        "url": "https://jalammar.github.io/illustrated-word2vec/",
        "source": "blog",
        "score": 0.91,
        "selected": True,
    },
    {
        "concept_name": "Attention",
        "title": "Visualizing A Neural Machine Translation Model",
        "url": "https://jalammar.github.io/visualizing-neural-machine-translation-mechanics-of-seq2seq-models-with-attention/",
        "source": "blog",
        "score": 0.93,
        "selected": True,
    },
    {
        "concept_name": "Self-Attention",
        "title": "The Illustrated Transformer",
        "url": "https://jalammar.github.io/illustrated-transformer/",
        "source": "blog",
        "score": 0.97,
        "selected": True,
    },
    {
        "concept_name": "Transformer Architecture",
        "title": "Attention Is All You Need",
        "url": PAPER_PDF,
        "source": "arxiv",
        "score": 0.99,
        "selected": True,
    },
]

DEMO_USER = str(DEMO_USER_ID)

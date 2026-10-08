-- Local demo user. Password: demo-password
-- Email: demo@reborn.local
-- Do not run this insert against a hosted project; use the Auth admin API there.

insert into auth.users (
  instance_id,
  id,
  aud,
  role,
  email,
  encrypted_password,
  email_confirmed_at,
  raw_app_meta_data,
  raw_user_meta_data,
  created_at,
  updated_at,
  confirmation_token,
  email_change,
  email_change_token_new,
  recovery_token
) values (
  '00000000-0000-0000-0000-000000000000',
  '11111111-1111-4111-8111-111111111111',
  'authenticated',
  'authenticated',
  'demo@reborn.local',
  extensions.crypt('demo-password', extensions.gen_salt('bf')),
  now(),
  '{"provider":"email","providers":["email"]}',
  '{"display_name":"Demo"}',
  now(),
  now(),
  '',
  '',
  '',
  ''
);

insert into auth.identities (
  id,
  user_id,
  identity_data,
  provider,
  provider_id,
  last_sign_in_at,
  created_at,
  updated_at
) values (
  '11111111-1111-4111-8111-111111111111',
  '11111111-1111-4111-8111-111111111111',
  '{"sub":"11111111-1111-4111-8111-111111111111","email":"demo@reborn.local"}',
  'email',
  '11111111-1111-4111-8111-111111111111',
  now(),
  now(),
  now()
);

insert into public.missions (
  id,
  user_id,
  goal,
  target_title,
  status
) values (
  '22222222-2222-4222-8222-222222222222',
  '11111111-1111-4111-8111-111111111111',
  'I want to understand the paper ''Attention Is All You Need''',
  'Attention Is All You Need',
  'learning'
);

insert into public.world_state (mission_id, state)
values (
  '22222222-2222-4222-8222-222222222222',
  $json$
  {
    "goal": "I want to understand the paper 'Attention Is All You Need'",
    "browser": {"open": false, "url": null, "title": null, "tab": null},
    "target_paper": {
      "title": "Attention Is All You Need",
      "url": "https://arxiv.org/abs/1706.03762"
    },
    "pdf": {
      "url": "https://arxiv.org/pdf/1706.03762",
      "title": "Attention Is All You Need"
    },
    "current_knowledge": "",
    "prerequisites": [
      "Sequence-to-Sequence",
      "Encoder-Decoder",
      "Word Embeddings",
      "Attention",
      "Self-Attention",
      "Transformer Architecture",
      "Multi-Head Attention + Positional Encoding"
    ],
    "resources": [
      {"title": "Sequence to Sequence Learning with Neural Networks", "url": "https://arxiv.org/abs/1409.3215", "source": "arxiv", "score": 0.9, "selected": true},
      {"title": "The Illustrated Word2vec", "url": "https://jalammar.github.io/illustrated-word2vec/", "source": "blog", "score": 0.91, "selected": true},
      {"title": "Visualizing A Neural Machine Translation Model", "url": "https://jalammar.github.io/visualizing-neural-machine-translation-mechanics-of-seq2seq-models-with-attention/", "source": "blog", "score": 0.93, "selected": true},
      {"title": "The Illustrated Transformer", "url": "https://jalammar.github.io/illustrated-transformer/", "source": "blog", "score": 0.97, "selected": true},
      {"title": "Attention Is All You Need", "url": "https://arxiv.org/pdf/1706.03762", "source": "arxiv", "score": 0.99, "selected": true}
    ]
  }
  $json$::jsonb
);

insert into public.concepts (id, mission_id, name, level, explanation, order_index, status)
values
  (
    '33333333-3333-4333-8333-333333333301',
    '22222222-2222-4222-8222-222222222222',
    'Sequence-to-Sequence',
    1,
    'A model that reads a whole input sequence, then writes an output sequence one piece at a time. Machine translation used this pattern before transformers.',
    1,
    'active'
  ),
  (
    '33333333-3333-4333-8333-333333333302',
    '22222222-2222-4222-8222-222222222222',
    'Encoder-Decoder',
    1,
    'The encoder turns the input into a compact representation. The decoder reads that representation and produces the output sequence.',
    2,
    'pending'
  ),
  (
    '33333333-3333-4333-8333-333333333303',
    '22222222-2222-4222-8222-222222222222',
    'Word Embeddings',
    1,
    'Each word is stored as a list of numbers. Words used in similar ways end up with similar lists, so the model can compare meaning.',
    3,
    'pending'
  ),
  (
    '33333333-3333-4333-8333-333333333304',
    '22222222-2222-4222-8222-222222222222',
    'Attention',
    2,
    'Instead of squeezing the whole input into one vector, the model looks back at the input positions that matter for the word it is writing now.',
    4,
    'pending'
  ),
  (
    '33333333-3333-4333-8333-333333333305',
    '22222222-2222-4222-8222-222222222222',
    'Self-Attention',
    2,
    'Each word looks at the other words in the same sentence and builds a new representation from the ones that are relevant.',
    5,
    'pending'
  ),
  (
    '33333333-3333-4333-8333-333333333306',
    '22222222-2222-4222-8222-222222222222',
    'Transformer Architecture',
    3,
    'The paper replaces recurrence with a stack of encoder and decoder blocks. Each block is built from attention and a small feed-forward network.',
    6,
    'pending'
  ),
  (
    '33333333-3333-4333-8333-333333333307',
    '22222222-2222-4222-8222-222222222222',
    'Multi-Head Attention + Positional Encoding',
    3,
    'Several attention heads look for different relationships at the same time. Positional encoding adds word order, because attention by itself does not know which word came first.',
    7,
    'pending'
  );

insert into public.resources (id, mission_id, concept_id, title, url, source, score, selected)
values
  (
    '44444444-4444-4444-8444-444444444401',
    '22222222-2222-4222-8222-222222222222',
    '33333333-3333-4333-8333-333333333301',
    'Sequence to Sequence Learning with Neural Networks',
    'https://arxiv.org/abs/1409.3215',
    'arxiv',
    0.90,
    true
  ),
  (
    '44444444-4444-4444-8444-444444444402',
    '22222222-2222-4222-8222-222222222222',
    '33333333-3333-4333-8333-333333333303',
    'The Illustrated Word2vec',
    'https://jalammar.github.io/illustrated-word2vec/',
    'blog',
    0.91,
    true
  ),
  (
    '44444444-4444-4444-8444-444444444403',
    '22222222-2222-4222-8222-222222222222',
    '33333333-3333-4333-8333-333333333304',
    'Visualizing A Neural Machine Translation Model',
    'https://jalammar.github.io/visualizing-neural-machine-translation-mechanics-of-seq2seq-models-with-attention/',
    'blog',
    0.93,
    true
  ),
  (
    '44444444-4444-4444-8444-444444444404',
    '22222222-2222-4222-8222-222222222222',
    '33333333-3333-4333-8333-333333333305',
    'The Illustrated Transformer',
    'https://jalammar.github.io/illustrated-transformer/',
    'blog',
    0.97,
    true
  ),
  (
    '44444444-4444-4444-8444-444444444405',
    '22222222-2222-4222-8222-222222222222',
    '33333333-3333-4333-8333-333333333306',
    'Attention Is All You Need',
    'https://arxiv.org/pdf/1706.03762',
    'arxiv',
    0.99,
    true
  );

insert into public.agent_events (mission_id, type, message, payload)
values (
  '22222222-2222-4222-8222-222222222222',
  'path_ready',
  'Learning path is ready for Attention Is All You Need.',
  '{"concepts":7,"resources":5}'::jsonb
);

update public.character_state
set mood = 'calm',
    animation = 'idle_sit',
    speech = 'Ready to walk through Attention Is All You Need.'
where user_id = '11111111-1111-4111-8111-111111111111';

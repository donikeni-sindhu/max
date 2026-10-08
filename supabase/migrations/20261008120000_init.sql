-- REBORN schema.
-- Users read and write only their own rows (auth.uid()).
-- The backend uses the service role key, which bypasses RLS.

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create or replace function public.mission_owned(target_mission uuid)
returns boolean
language sql
stable
security invoker
set search_path = public
as $$
  select exists (
    select 1
    from public.missions
    where id = target_mission
      and user_id = auth.uid()
  );
$$;

create table public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  display_name text,
  created_at timestamptz not null default now()
);

create table public.missions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles (id) on delete cascade,
  goal text not null,
  target_title text,
  status text not null default 'created'
    check (status in ('created', 'planning', 'researching', 'learning', 'complete', 'failed', 'cancelled')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.world_state (
  mission_id uuid primary key references public.missions (id) on delete cascade,
  state jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now(),
  constraint world_state_shape check (
    state ? 'goal'
    and state ? 'browser'
    and state ? 'target_paper'
    and state ? 'pdf'
    and state ? 'current_knowledge'
    and state ? 'prerequisites'
    and jsonb_typeof(state -> 'prerequisites') = 'array'
    and state ? 'resources'
    and jsonb_typeof(state -> 'resources') = 'array'
  )
);

create table public.concepts (
  id uuid primary key default gen_random_uuid(),
  mission_id uuid not null references public.missions (id) on delete cascade,
  name text not null,
  level integer not null check (level between 1 and 3),
  explanation text not null default '',
  order_index integer not null,
  status text not null default 'pending'
    check (status in ('pending', 'active', 'done'))
);

create table public.resources (
  id uuid primary key default gen_random_uuid(),
  mission_id uuid not null references public.missions (id) on delete cascade,
  concept_id uuid references public.concepts (id) on delete set null,
  title text not null,
  url text not null,
  source text,
  score numeric,
  selected boolean not null default false
);

create table public.agent_events (
  id bigserial primary key,
  mission_id uuid not null references public.missions (id) on delete cascade,
  type text not null,
  message text not null,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table public.character_state (
  user_id uuid primary key references public.profiles (id) on delete cascade,
  mood text not null default 'calm',
  animation text not null default 'idle_sit',
  speech text not null default '',
  updated_at timestamptz not null default now()
);

create index missions_user_id_idx on public.missions (user_id);
create index concepts_mission_id_idx on public.concepts (mission_id, order_index);
create index resources_mission_id_idx on public.resources (mission_id);
create index resources_concept_id_idx on public.resources (concept_id);
create index agent_events_mission_id_idx on public.agent_events (mission_id, created_at);

create trigger missions_set_updated_at
  before update on public.missions
  for each row execute function public.set_updated_at();

create trigger world_state_set_updated_at
  before update on public.world_state
  for each row execute function public.set_updated_at();

create trigger character_state_set_updated_at
  before update on public.character_state
  for each row execute function public.set_updated_at();

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, display_name)
  values (
    new.id,
    coalesce(new.raw_user_meta_data ->> 'display_name', split_part(new.email, '@', 1), 'Learner')
  );
  insert into public.character_state (user_id)
  values (new.id);
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

alter table public.profiles enable row level security;
alter table public.missions enable row level security;
alter table public.world_state enable row level security;
alter table public.concepts enable row level security;
alter table public.resources enable row level security;
alter table public.agent_events enable row level security;
alter table public.character_state enable row level security;

create policy profiles_own on public.profiles
  for all to authenticated
  using (id = auth.uid())
  with check (id = auth.uid());

create policy missions_own on public.missions
  for all to authenticated
  using (user_id = auth.uid())
  with check (user_id = auth.uid());

create policy world_state_own on public.world_state
  for all to authenticated
  using (public.mission_owned(mission_id))
  with check (public.mission_owned(mission_id));

create policy concepts_own on public.concepts
  for all to authenticated
  using (public.mission_owned(mission_id))
  with check (public.mission_owned(mission_id));

create policy resources_own on public.resources
  for all to authenticated
  using (public.mission_owned(mission_id))
  with check (public.mission_owned(mission_id));

create policy agent_events_own on public.agent_events
  for all to authenticated
  using (public.mission_owned(mission_id))
  with check (public.mission_owned(mission_id));

create policy character_state_own on public.character_state
  for all to authenticated
  using (user_id = auth.uid())
  with check (user_id = auth.uid());

grant select, insert, update, delete on
  public.profiles,
  public.missions,
  public.world_state,
  public.concepts,
  public.resources,
  public.agent_events,
  public.character_state
to authenticated;

grant select, insert, update, delete on
  public.profiles,
  public.missions,
  public.world_state,
  public.concepts,
  public.resources,
  public.agent_events,
  public.character_state
to service_role;

grant usage, select on sequence public.agent_events_id_seq to authenticated, service_role;

alter table public.missions replica identity full;
alter table public.world_state replica identity full;
alter table public.concepts replica identity full;
alter table public.agent_events replica identity full;
alter table public.character_state replica identity full;

alter publication supabase_realtime add table public.missions;
alter publication supabase_realtime add table public.world_state;
alter publication supabase_realtime add table public.concepts;
alter publication supabase_realtime add table public.agent_events;
alter publication supabase_realtime add table public.character_state;

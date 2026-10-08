# Character art

Drop frame images or one sprite sheet in this folder, then point
`widget/src/character/manifest.ts` at those files.

Every animation starts as `null`. While an entry is `null`, the widget draws
the white placeholder blob. Filling an entry does not require any other code change.

Frame clip:

```ts
idle_sit: { frames: ['/src/assets/character/idle-1.png'], fps: 8, loop: true }
```

Sprite sheet:

```ts
walk_right: {
  sheet: '/src/assets/character/walk.png',
  frameWidth: 128,
  frameHeight: 128,
  frames: 6,
  fps: 12,
  loop: true,
}
```

# Перевірка підпису A03–A05

Маніфест `ACTS.sha256` прив’язує протоколи, докази й акти до хешів розпакованих результатів. Підпис створено делеговано чинним локальним ключем автора. Відбиток ключа `SHA256:w7ynAVmM58JG9ksD/CaRjP+6k4AMb0pF2MW362VyhEc`. Для підтвердження особи звірте відбиток із відомим вам ключем автора.

```sh
cd research/identification
ssh-keygen -Y verify -f evidence/allowed_signers -I neuron7x \
  -n neuron7x.research.v1 -s evidence/ACTS.sha256.sig < evidence/ACTS.sha256
sha256sum --check evidence/ACTS.sha256
```

Запечатані результати й механістичні розрахунки перевіряє `test_identification_limits.py`.

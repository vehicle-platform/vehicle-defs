# LLM benchmark: qwen2.5-1.5b pi5 2t

| metric | value |
|---|---|
| prompts | 10 |
| errors | 0 |
| number-grounded answers | 9 / 10 |
| time to first token, median / p95 (s) | 2.77 / 3.19 |
| total latency, median / p95 (s) | 6.57 / 11.30 |
| generation speed, median (tokens/s) | 6.5 |

| # | question | TTFT s | total s | tok/s | numbers | answer |
|---|---|---|---|---|---|---|
| 1 | Son sürüşümde en yüksek hızım neydi? | 0.13 | 3.05 | 6.5 | ok | Son sürüşümde en yüksek hızınız 112.4 km/h idi. |
| 2 | Son sürüşüm kaç kilometreydi, ne kadar sürdü? | 2.86 | 6.69 | 6.5 | ok | Son sürüşüm 42.8 km uzaklıktı ve sürdü 51 dakika sürdü. |
| 3 | Motor sıcaklığı normal mi? | 2.50 | 4.06 | 6.4 | ok | Motor sıcaklığı 92°C'dir. |
| 4 | Motor ne kadar ısındı en fazla? | 2.90 | 5.13 | 6.7 | ok | Motor ısındı en fazla 118 derece. |
| 5 | Akü gerilimi nasıl? | 2.32 | 6.61 | 6.5 | ok | Akü gerilimi 12.6V ve yüklenme gerilimi 14.2V oluyor. |
| 6 | Lastik basınçlarım nedir? | 2.32 | 7.08 | 6.5 | ok | Sonuç: Front lastik basınçınız 225 kPa ve rear lastik basınçınız 250 kPa'dır. |
| 7 | Ortalama yakıt tüketimim kaç? | 3.13 | 6.53 | 6.5 | UNGROUNDED 100 | Ortalama yakıt tüketiminiz 3.4 litre 100 kmdir. |
| 8 | Bu sürüşte en çok ne kadar yattım? | 3.19 | 6.79 | 6.7 | ok | Sürücü, bu sürüşte en çok 38.5 derece yüksek düşme yaptınız. |
| 9 | Hangi arıza kodları var? | 2.99 | 11.30 | 6.5 | ok | Arıza kodu P0171, "Fuel trim lean, bank 1" olarak bulunuyor. Bu kod, motorun gerilim kontrolü (fuel trim) bank 1 aralığında eksik olduğu anlamına gelir. |
| 10 | Toplam kaç kilometre yaptım? | 2.68 | 4.71 | 6.4 | ok | Toplam 12874 kilometre yaptınız. |

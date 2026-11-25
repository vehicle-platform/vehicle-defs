# LLM benchmark: qwen2.5-1.5b mac-m1 cpu 2t

| metric | value |
|---|---|
| prompts | 10 |
| errors | 0 |
| number-grounded answers | 9 / 10 |
| time to first token, median / p95 (s) | 0.46 / 1.09 |
| total latency, median / p95 (s) | 1.32 / 4.86 |
| generation speed, median (tokens/s) | 33.8 |

| # | question | TTFT s | total s | tok/s | numbers | answer |
|---|---|---|---|---|---|---|
| 1 | Son sürüşümde en yüksek hızım neydi? | 0.03 | 0.53 | 37.9 | ok | Son sürüşümde en yüksek hızınız 112.4 km/h idi. |
| 2 | Son sürüşüm kaç kilometreydi, ne kadar sürdü? | 0.46 | 0.98 | 42.3 | ok | Sürücü, son sürüşünden 42.8 km uzaklık gösteriyor. |
| 3 | Motor sıcaklığı normal mi? | 0.41 | 1.36 | 42.2 | ok | Motor sıcaklığı 92 derece ve yağ sıcaklığı 104 derece oluyor. Motoru kontrol etmeyi önermeyi tercih ederim. |
| 4 | Motor ne kadar ısındı en fazla? | 0.44 | 0.81 | 40.3 | ok | Motor ısındı en fazla 118 derece. |
| 5 | Akü gerilimi nasıl? | 0.45 | 1.38 | 29.1 | ok | Akü gerilimi 12.6V ve yüklenme gerilimi 14.2V'dir. |
| 6 | Lastik basınçlarım nedir? | 0.37 | 1.20 | 37.2 | ok | Sonuç: Front lastik basınçınız 225 kPa ve rear lastik basınçınız 250 kPa'dır. |
| 7 | Ortalama yakıt tüketimim kaç? | 0.57 | 1.33 | 30.4 | UNGROUNDED 100 | Ortalama yakıt tüketiminiz 3.4 litre 100 km'de. |
| 8 | Bu sürüşte en çok ne kadar yattım? | 1.09 | 1.92 | 16.9 | ok | Üzgünüm, bu araç sonucunda veri yok. |
| 9 | Hangi arıza kodları var? | 1.09 | 4.86 | 13.8 | ok | Arıza kodu P0171, "Fuel trim lean, bank 1" olarak bulunuyor. Bu kod, motorun gerilim kontrolü (fuel trim) bank 1 aralığında eksik olduğunu gösteriyor. |
| 10 | Toplam kaç kilometre yaptım? | 0.68 | 1.31 | 20.6 | ok | Toplam 12874 kilometre yaptınız. |

# LLM benchmark: gemma3-4b-pi5

| metric | value |
|---|---|
| prompts | 10 |
| errors | 0 |
| number-grounded answers | 9 / 10 |
| time to first token, median / p95 (s) | 16.45 / 17.51 |
| total latency, median / p95 (s) | 29.90 / 35.90 |
| generation speed, median (tokens/s) | 3.6 |

| # | question | TTFT s | total s | tok/s | numbers | answer |
|---|---|---|---|---|---|---|
| 1 | Son sürüşümde en yüksek hızım neydi? | 0.74 | 16.09 | 3.6 | ok | Son sürüşünüzde en yüksek hızınız 112.4 kmh idi. Ortalama hızınız ise 58.7 kmh olmuş. Güvenliğiniz için, lütfen motorunuzu kontrol ettirmek üzere bir servise uğrayın. |
| 2 | Son sürüşüm kaç kilometreydi, ne kadar sürdü? | 16.81 | 29.64 | 3.6 | ok | Son sürüşünüzde 42,8 kilometre yol katettiniz. Bu yolculuk yaklaşık 51 dakika sürdü. Güvenli bir yerde durup motoru kontrol ettirmenizi tavsiye ederim. |
| 3 | Motor sıcaklığı normal mi? | 16.36 | 32.60 | 3.6 | ok | Motorun soğutma sıvısı sıcaklığı 92 derece, motor yağı sıcaklığı ise 104 derecedir. Bu değerler normal sınırlar içinde görünüyor. Güvenlik için, lütfen motoru kontrol ettirmek üzere bir servise uğrayın. |
| 4 | Motor ne kadar ısındı en fazla? | 16.89 | 30.16 | 3.5 | ok | Motorun en fazla 121 dereceye kadar ısınabilmesi mümkündür. Şu anda 118 derece civarında. Güvenli bir yerde durup motoru kontrol ettirmemizi tavsiye ederim. |
| 5 | Akü gerilimi nasıl? | 15.59 | 27.29 | 3.6 | ok | Akü gerilimi 12.6 volt civarında. Şarj voltajı ise 14.2 volt. Kontrol için bir servise danışmanızı tavsiye ederim. |
| 6 | Lastik basınçlarım nedir? | 15.59 | 27.11 | 3.6 | ok | Ön lastikleriniz 225 kPa, arka lastikleriniz ise 250 kPa. Bu değerler genellikle motosikletinizin kullanım kılavuzunda belirtilen aralıktadır. |
| 7 | Ortalama yakıt tüketimim kaç? | 17.51 | 35.90 | 3.5 | UNGROUNDED 100 | Ortalama yakıt tüketimin 3.4 litre/100km civarında. 42.8 km'lik bir yolculukta 1.46 litre yakıt harcadın. Güvenlik için, sonuçta advise_stop true ise motorunu kontrol ettirmeyi öneririm. |
| 8 | Bu sürüşte en çok ne kadar yattım? | 17.11 | 30.22 | 3.6 | ok | Sürüşünüzde maksimum yana eğim 38.5 dereceydi. Ayrıca iki kez sert fren yaptığınız tespit edildi. Güvenlik için, lütfen motorunuzu kontrol ettirmek üzere güvenli bir yere durun. |
| 9 | Hangi arıza kodları var? | 16.54 | 33.01 | 3.6 | ok | Arıza kodu P0171, bank 1'de yakıt ayarının kuru olduğunu gösteriyor. Bu, genellikle yakıt sistemiyle ilgili bir soruna işaret eder. Güvenlik nedeniyle, lütfen motoru kontrol ettirmek için advise_stop true durumuna geçin. |
| 10 | Toplam kaç kilometre yaptım? | 15.98 | 28.32 | 3.6 | ok | 12874 kilometre yapmışsınız. Servis yapmanız gerekiyor, 14000 kilometrelere ulaştınız. Güvenli bir yerde durup motoru kontrol ettirmek iyi olur. |

# LLM benchmark: gemma3-1b-pi5

| metric | value |
|---|---|
| prompts | 10 |
| errors | 0 |
| number-grounded answers | 9 / 10 |
| time to first token, median / p95 (s) | 8.46 / 9.00 |
| total latency, median / p95 (s) | 13.14 / 14.19 |
| generation speed, median (tokens/s) | 9.9 |

| # | question | TTFT s | total s | tok/s | numbers | answer |
|---|---|---|---|---|---|---|
| 1 | Son sürüşümde en yüksek hızım neydi? | 0.31 | 2.44 | 9.9 | ok | Sürüşünüzde en yüksek hızınız 112.4 km/h oldu. |
| 2 | Son sürüşüm kaç kilometreydi, ne kadar sürdü? | 8.76 | 13.06 | 10.0 | ok | Sürüşünüz 42.8 kilometreye ulaştı. Yaklaşık 51 dakika sürdünüz. Güvenliğiniz için, motorunuzun kontrolünü kontrol etmeniz önerilir. |
| 3 | Motor sıcaklığı normal mi? | 8.46 | 13.30 | 9.9 | ok | Motor sıcaklığı normal. Sıcaklık değeri 92 derece civarındır. Motorun ısınması normal bir durumdur. Eğer sıcaklık çok yüksekse, lütfen motoru kontrol edin ve güvenli bir yere durun. |
| 4 | Motor ne kadar ısındı en fazla? | 8.66 | 12.60 | 9.9 | ok | Motorunuz 118 derecelere ulaştı. En yüksek sıcaklık 121 derecedir. Güvenliğiniz için motoru kontrol ettirmeyi unutmayın. |
| 5 | Akü gerilimi nasıl? | 8.01 | 13.80 | 10.0 | ok | Akü gerilimi 12.6 volt ve 14.2 volt arasında. Bu değerler normal sınırlar içinde. Eğer gerilim düşüyorsa, aküde bir sorun olabilir. Güvenli bir yere geçip motoru kontrol etmenizi öneririm. |
| 6 | Lastik basınçlarım nedir? | 8.01 | 9.81 | 10.0 | ok | "Lastik basıncınız 225 ve 250 pa arasında." |
| 7 | Ortalama yakıt tüketimim kaç? | 9.00 | 14.19 | 9.8 | UNGROUNDED 100 | Yakıt tüketiminiz 3.4 litre/100km civarındadır. Bu değer, son 42.8 km'lik yolculukta oluşmuştur. Yakıt tüketimini kontrol ettirmenizi öneririm. |
| 8 | Bu sürüşte en çok ne kadar yattım? | 8.81 | 13.21 | 10.0 | ok | Sürüşünüzde 38.5 derece lean var. Motorunuzun kontrolünü sağlayın ve güvenli bir yere durun. Eğer sonuçta_stop doğruysa, güvenli bir yerde durun. |
| 9 | Hangi arıza kodları var? | 8.46 | 13.99 | 9.9 | ok | "Motorunuzda bir sorun var gibi görünüyor. Özellikle bank 1'de bir sorun olabilir. Motoru kontrol ettirmenizi öneririm. Eğer sorun devam ederse, güvenli bir yere durup motoru kontrol etmeniz en doğrusu olacaktır." |
| 10 | Toplam kaç kilometre yaptım? | 8.25 | 9.50 | 9.6 | ok | 12874 kilometre yoluna çıktınız. |

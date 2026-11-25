# 2026-11-25 — Gemma 3 4B IT (third run)

Same prompts, tool and Pi as [run 1](../2026-11-25-qwen2.5-1.5b/README.md) and [run 2](../2026-11-25-gemma3-1b/README.md); only the model changed.

## Conditions

| | Raspberry Pi 5 |
|---|---|
| Hardware / OS / llama.cpp / unit | as in run 1 (Pi 5 8 GB, trixie, llama-server v1.0.0 b1b770d, `vehicle-llama.service` with `CPUQuota=150%`, 2 threads, ctx 2048) |
| Model | `gemma-3-4b-it-Q4_K_M.gguf`, SHA-256 `882e8d2d…21a0863` (Hugging Face `ggml-org/gemma-3-4b-it-GGUF` @ d0976223), Gemma terms of use |
| Power / cooling | non-27 W adapter, `get_throttled=0x50000` since boot; Active Cooler, fan 4869 rpm, 58.2 °C after the run |
| Bench tool | vehicle-linux-node @ 3a8ddca, `--warmup 1 --timeout 180` |

## Results

| Metric (Pi 5) | Qwen2.5-1.5B (run 1) | Gemma 3 1B (run 2) | Gemma 3 4B (this run) |
|---|---|---|---|
| Number-grounded answers | 9/10 | 9/10 | 9/10 |
| TTFT median / p95 (s) | 2.77 / 3.19 | 8.46 / 9.00 | 16.45 / 17.51 |
| Total latency median / p95 (s) | 6.57 / 11.30 | 13.14 / 14.19 | 29.90 / 35.90 |
| Generation speed median (tok/s) | 6.5 | 9.9 | 3.6 |

Raw output: `gemma3-4b-pi5.json|md`.

## Human review of the Turkish (Claude, 2026-11-25)

The most natural Turkish of the three (correct grammar, units kept: "Ön lastikleriniz 225 kPa" ("Your front tires are 225 kPa")), but:

- it computes on its own: "42.8 km'lik bir yolculukta 1.46 litre yakıt harcadın" ("on a 42.8 km trip you burned 1.46 litres of fuel") (#7), against invariant 7; the number guard did not flag it;
- a false claim from a number in the result: "Servis yapmanız gerekiyor, 14000 kilometrelere ulaştınız" ("You need to have a service, you have reached 14000 kilometres") at 12874 km (#10);
- unsolicited service/stop advice in nearly every answer; internal field names read out ("advise_stop true", #7, #9; internal field name "advise_stop");
- decimal point instead of comma in most answers.


## Prompts and answers (English translation)

Literal translation for readers; the evaluated output is the Turkish text in the raw files.

| # | Question (EN) | Answer (EN, literal) | Note |
|---|---|---|---|
| 1 | What was my top speed on my last ride? | In your last ride your top speed was 112.4 kmh. Your average speed was 58.7 kmh. For your safety, please stop by a service to have your engine checked. | Unsolicited advice |
| 2 | How many kilometres was my last ride and how long did it take? | In your last ride you covered 42,8 kilometres of road. This trip lasted about 51 minutes. I recommend stopping at a safe place and having the engine checked. | Unsolicited advice |
| 3 | Is the engine temperature normal? | The engine's coolant temperature is 92 degrees, the engine oil temperature is 104 degrees. These values seem within normal limits. For safety, please stop by a service to have the engine checked. | Unsolicited advice |
| 4 | How hot did the engine get at most? | It is possible for the engine to heat up to at most 121 degrees. Currently around 118 degrees. I recommend stopping at a safe place and having the engine checked by us. | Advice; mixed person ("by us"); misreads max as capability |
| 5 | How is the battery voltage? | Battery voltage is around 12.6 volts. Charging voltage is 14.2 volts. I recommend you consult a service for checking. | Unsolicited advice |
| 6 | What are my tire pressures? | Your front tires are 225 kPa, your rear tires are 250 kPa. These values are generally in the range stated in your motorcycle's user manual. | Ungrounded claim about the manual |
| 7 | What is my average fuel consumption? | Your average fuel consumption is around 3.4 litres/100km. On a 42.8 km trip you (informal) burned 1.46 litres of fuel. For safety, if advise_stop is true in the result, I recommend having your engine checked. | Own arithmetic (1.46 l); internal field name leaked; advice; mixed formality |
| 8 | How much did I lean at most on this ride? | In your ride the maximum lean was 38.5 degrees. Also it was detected that you braked hard twice. For safety, please stop at a safe place to have your engine checked. | Unsolicited advice; hard-braking claim not asked for |
| 9 | Which fault codes are there? | Fault code P0171 shows that the fuel setting in bank 1 is dry. This generally points to a problem with the fuel system. For safety reasons, please switch to the advise_stop true state to have the engine checked. | Internal field name leaked; advice; garbled |
| 10 | How many kilometres have I done in total? | You have done 12874 kilometres. You need to have a service, you have reached 14000 kilometres. It would be good to stop at a safe place and have the engine checked. | False claim: 14000 km at 12874 km; advice |

## Conclusions

1. Too slow on the Pi 5: about 30 s per phrasing call, about a minute per `/chat` answer with the tool-choice call.
2. Better wording does not make it safe: own arithmetic and a false service claim slip past the number guard.
3. Across runs 1-3 no local model is fit for riders as is. Next steps for the assistant: keyword-first tool
   choice, deterministic templates for the frequent questions, an output filter (advice sentences, internal names,
   numbers not copied from the result), cloud providers (D-124) for quality with the local model as fallback,
   and newer small models measured with this same set.

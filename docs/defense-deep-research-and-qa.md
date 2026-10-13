# PLDHE — Deep Research Report + Defense Q&A

> **Defense target: ~Oct 17, 2026 (4 days).**
> Ye document 2 kaam karta hai: (1) tumhare project ke peeche **real research** — verified facts, real systems, real papers — taake panel ke saamne har claim ke peeche saboot ho; (2) **15 mushkil sawal + unke mazboot jawab**, jo panel sab se zyada puchta hai.
>
> Rule: jo claim yahan likha hai, wo defense mein bolo. Jo yahan "mat bolo" section mein hai, wo mat bolo. Bas.

---

## PART 1 — DEEP RESEARCH (verified 2026-10-13)

### 1. The helpline is REAL — and documented

Punjab Livestock & Dairy Development Department ka toll-free helpline **08000-9211** hai — 24/7, aur ye **SPMS-9211** ticketing system ka hissa hai (farmer registration, har complaint ek ticket banti hai, field staff ko forward hoti hai).

Sources:
- Punjab government ki official helplines list: https://punjab.gov.pk/index.php/helplines ("Livestock & Dairy Development — 0800-09211 — Active")
- Detail write-up (kya poochte hain jab call karo: naam, CNIC, mobile, gaon/union council/tehsil, janwar ki tafseel, alamat): https://pakera.pk/get-free-animal-treatment-punjab/
- Livestock Card scheme bhi isi helpline par chalti hai: https://mmnews.tv/heres-how-to-apply-for-punjab-livestock-card/

**Defense mein iska matlab:** tumhara "crown jewel" proxy-call module kisi imaginary number par nahi — ek documented government system par target karta hai. Slide par helpline page ka screenshot + SPMS ticket flow dikhao. Yehi tumhara sab se concrete proof-of-relevance hai.

**Ek imandari wali baat:** complaint register karne ke liye operator ko CNIC + gaon/UC/tehsil chahiye hota hai — isi liye tumhara **location resolver** (GPS → tehsil/chak → operator-proof address) core feature hai, side feature nahi. Panel ko ye link samjhao.

### 2. Saraiki speech recognition — the honest technical story

**Fact:** OpenAI Whisper ~99 languages support karta hai; **Saraiki officially supported nahi hai.** Ye kamzori nahi — ye tumhara research problem statement hai.

**Supporting evidence (real papers):**
- Whisper cross-lingual transfer (Cambridge, 2024): experiments show Whisper "can map utterances from unseen languages into the same shared speech embedding" — i.e., model ne kabhi na dekhi zuban bhi shared embedding space mein map ho jati hai. http://arxiv.org/pdf/2407.01130v1
- Low-resource dialect fine-tuning (MDPI, Sep 2026): Whisper large-v3-turbo par **LoRA fine-tuning** (sirf ~0.7% parameters update) ne dialectal speech par **WER 57–70% kam** kiya — Standard se dialect tak ka gap parameter-efficient adaptation se bridge hota hai. https://www.mdpi.com/2076-3417/16/19/9635

**Tumhara pipeline (already implemented):**
1. Urdu-base Whisper model + Saraiki system prompt (prompt biasing)
2. Dialect normalization layer (`backend/app/language.py`)
3. **Har intake call = training data** — corpus-collection loop (`docs/multilingual-stt.md`) → future LoRA fine-tune

**Defense line (yaad kar lo):** *"Saraiki Whisper mein nahi hai — isi liye humne transfer-learning pipeline banayi. Har live call hamara corpus barhati hai, aur LoRA fine-tuning se WER 57–70% tak gir sakta hai, jaisa low-resource dialects par published results dikhate hain."*

### 3. Jo pehle se mojood hai — related systems (imandari + differentiation)

| System | Kya karta hai | Kya NAHI karta (tumhara gap) |
|---|---|---|
| **SPMS-9211 helpline** (Govt. Punjab) | Human operators, complaint tickets | Koi AI triage nahi; proactive outreach nahi; Saraiki support nahi |
| **Kissan Dost Bashir** (Telenor, 7272 — launched ~May 2026) | AI voice bot: mandi rates, weather advisory, livestock guidance | **Sirf Urdu**; advisory-only (koi case/ticket management nahi); koi government complaint filing nahi |
| **KissanBot** (Concave AGRI) | Urdu chatbot, crops (rice/wheat/maize) Q&A, RAG-based | Crops-focused; livestock triage nahi; voice-call automation nahi |
| **iCow** (Kenya) | SMS-based livestock tips | SMS era; voice AI nahi; Pakistan-specific nahi |
| **FAO EMPRES-i** | Global animal-disease surveillance | Top-down system; farmer-facing intake nahi |
| Image classifiers (MDPI Apr 2026) | LSD **98.36%**, FMD **99.84%** accuracy (internal validation, ensemble CNNs) | Sirf images; voice intake, dispatch, helpline integration kuch nahi |

Sources: https://www.arabnews.pk/pakistan/pakistan-telecom-operator-launches-ai-powered-agriculture-bot-to-promote-smart-farming-2641002 · https://sybrid.com/resources/blog/ai-chatbots-pakistan/ · https://www.mdpi.com/2673-2688/7/4/137

**Ayon et al. (2024)** ne 10,516 expert-annotated images par dikhaya ke LSD/FMD ke symptoms overlap karte hain (insect bites/chemical burns se bhi) — ensemble model ne 98.2% accuracy hasil ki. Ye tumhare **future computer-vision module** ka literature ground hai. https://www.researchgate.net/publication/377017285_Clinical_and_Molecular_Detections_of_Lumpy_Skin_Disease_Possibilities_of_Co-infection_with_Foot-and-Mouth_Disease

### 4. Novelty — tumhara project alag KYUN hai

Koi single module novel nahi hai. **Combination novel hai.** Koi existing system ye 4 cheezein ek saath nahi karta:

1. **Saraiki-first voice triage** — koi voice bot Saraiki mein livestock triage nahi karta (sab Urdu-only hain).
2. **Autonomous helpline proxy call** — AI agent khud 08000-9211 par call karke **asli complaint file** karta hai aur ticket number wapas lata hai. Ye advisory se agla step hai: *action*.
3. **Chak-level location resolver** — GPS → tehsil/chak → operator-proof professional address. SPMS operators "address nahi" keh kar complaint reject karte hain — ye us rejection ko khatam karta hai.
4. **GIS outbreak surveillance** — tehsil-level heatmap + cluster alerts. Koi farmer-facing system ye nahi deta.

**Defense mein ek line:** *"Kissan Dost mashwara deta hai. PLDHE mashwara + triage + sarkari complaint + outbreak map — chaaron ek pipeline mein."*

---

## PART 2 — DEFENSE Q&A (15 mushkil sawal, mazboot jawab)

### Q1. "Saraiki to Whisper mein hai hi nahi — tumhara claim jhoota hai?"
**Jawab:** "Bilkul sahi — Whisper mein Saraiki officially supported nahi hai, aur humne ye claim kabhi nahi kiya. Humne **transfer-learning pipeline** banayi hai: Urdu-base model + Saraiki prompt biasing + dialect normalization. Published research dikhati hai ke Whisper unseen languages ko shared embedding space mein map kar sakta hai (Cambridge 2024), aur LoRA fine-tuning se low-resource dialects par WER 57–70% girta hai (MDPI 2026). Hamara corpus-collection loop har call se training data banata hai — ye roadmap `docs/multilingual-stt.md` mein documented hai."

### Q2. "Ye to bas helpline ka number dial karna hai — is mein research kya hai?"
**Jawab:** "Dial karna trivial hai. Research 3 jagah hai: (a) **multilingual triage** — Saraiki/Punjabi/Urdu symptoms se risk classification; (b) **autonomous negotiation** — AI agent operator se administrative Urdu mein baat karke CNIC, location, symptoms de kar ticket number extract karta hai; (c) **chak-level addressing** — bina postal address wale dehat ko PostGIS se operator-acceptable address mein translate karna. Koi bhi hissa akela naya nahi — pipeline nayi hai."

### Q3. "Telenor ka Kissan Dost already hai — farq kya hai?"
**Jawab:** "Kissan Dost **advisory** hai — mashwara deta hai, Urdu mein. PLDHE **action** hai — triage karta hai, local vet dispatch karta hai, aur khud helpline par complaint file karke ticket number lata hai. Plus Saraiki-first, plus GIS outbreak map. Comparison table Part 1, Section 3 mein hai."

### Q4. "AI ghalat diagnose kare to zimmedar kaun?" (ethics — ye sawal zaroor aayega)
**Jawab:** "Hum **diagnosis ka claim nahi karte — triage ka karte hain.** Farq: triage = urgency rank karna (EMERGENCY/HIGH/MEDIUM/LOW), diagnosis = bimari ka naam pakka karna. EMERGENCY par bhi system khud ilaaj nahi batata — **farmer ki consent** se qareebi vet ko dispatch karta hai, aur home-remedy path sirf mild cases mein **safe palliative steps** deta hai (e.g., cold sponging), koi dawai prescribe nahi karta. Final authority hamesha vet/operator ke paas hai."

### Q5. "Live demo fail ho gaya to?"
**Jawab (aur backup plan):** "Demo ke 3 layers hain: (1) live Vapi call; (2) agar network issue ho to **recorded call playback**; (3) agar dono fail hon to **simulated transcript** par end-to-end pipeline — village extraction + triage — jo pehle se verified hai (`extract_village()` test: 'Chak 111' correctly extracted, FMD/EMERGENCY classified). Har layer pehle se tested hai."

### Q6. "Data kahan se aaya? Saraiki ka dataset kahan hai?"
**Jawab:** "Do tarah ka data: (a) **triage rules** — veterinary literature se (FMD: munh se jhaag/khur mein zakham; LSD: motay danay; HS/Gal Ghotu: galay mein sujan) — ye documented veterinary symptomatology hai; (b) **speech corpus** — abhi seedha fine-tune karne layak Saraiki corpus public mein nahi hai, isi liye humne **corpus-collection loop** design kiya hai: har intake call (consent ke saath) future training data banti hai. Ye honest limitation hai, aur future work mein LoRA fine-tuning isi corpus par hogi."

### Q7. "Automated call legal hai? Helpline wale robot se baat karenge?"
**Jawab:** "Assistant call ke shuru mein **khud ko AI agent ke tor par introduce** karta hai aur farmer ki taraf se authorized hone ka hawala deta hai — koi dhoka nahi. Operator ke paas har waqt call khatam karne ka ikhtiyar hai. Ye **farmer ki madad** ke liye hai — un farmers ke liye jo khud administrative Urdu mein complaint file nahi kar sakte. Consent-based, transparent automation hai."

### Q8. "14.5 million farmers — scale kaise hoga?"
**Jawab:** "Architecture stateless hai: FastAPI backend horizontally scale hota hai, PostGIS spatial queries indexed hain, aur voice calls Vapi ke infrastructure par hain (per-minute pricing). Pilot **Layyah district** hai — tehsil-level rollout ka plan hai, poora Punjab day-one ka claim nahi. Costing: Vapi ~$0.05–0.10/min; ek triage call ~3 min ≈ Rs 50 — government helpline ke muqable mein negligible."

### Q9. "PostGIS kyun? Google Maps kyun nahi?"
**Jawab:** "Do wajuhat: (a) **offline/rural** — dehat mein address system hi nahi; PostGIS humein custom tehsil/chak boundaries rakhne deta hai jo Google Maps mein nahi hain; (b) **surveillance** — outbreak heatmap aur cluster detection ke liye spatial queries (ST_Contains, ST_DWithin) database ke andar chahiye, har request par external API nahi. Plus open-source = zero licensing cost."

### Q10. "FMD aur LSD ke symptoms overlap karte hain — rule-based triage kaise handle karega?"
**Jawab:** "Sahi point — Ayon et al. (2024) ne 10,516 images par yehi overlap document kiya hai. Hamara rule engine **conservative** hai: agar symptoms overlap karen to higher risk level assign hota hai (better safe). Aur yehi wajah hai ke future work mein **image classifier** hai — MDPI 2026 ke ensemble models LSD par 98.36% aur FMD par 99.84% (internal validation) dikhate hain. Voice triage first filter hai, final word vet ka hai."

### Q11. "Dusre group ne bhi yehi idea liya — tumhara farq kya hai?"
**Jawab:** "Unka exact scope mujhe nahi pata — lekin hamare 4 differentiators (Part 1, Section 4) publicly documented hain: Saraiki-first voice, autonomous helpline proxy with ticket extraction, chak-level resolver, GIS outbreak map. Agar unka project in mein se koi **ek** bhi nahi karta, to hamara combination alag hai. (Tip: unka synopsis dekh lo — phir exact point-by-point farq bata sakte ho.)"

### Q12. "Cost? Vapi calls mehngi hain — farmer afford karega?"
**Jawab:** "Farmer kuch nahi deta — **pilot government/NGO-funded** model hai. Per-call cost ~Rs 50 (3-min call). Ek FMD outbreak se ek bhains ki qeemat lakhon mein hai — Rs 50 ki call se early triage aur timely vet dispatch us nuksan ko rokta hai. ROI obvious hai."

### Q13. "Farmer ka data — privacy?"
**Jawab:** "CNIC/location sirf complaint filing ke liye use hota hai — wahi data jo operator waise bhi mangta hai. Database mein minimal retention, aur corpus-collection ke liye **explicit consent**. Koi data third party ko nahi becha jata — ye design principle hai, baad ki soch nahi."

### Q14. "Evaluation metrics kya hain? Koi number hai?"
**Jawab (imandar numbers):** "Jo verified hai: triage engine **5/5 test cases pass** (FMD→EMERGENCY, LSD→HIGH, HS→EMERGENCY, mild→LOW, with explainable reasoning); village extraction test pass ('Chak 111' transcript se correctly extracted). Jo **claim nahi** karte: clinical accuracy percentage — uske liye field trial chahiye, jo future work hai. Hum inflated numbers nahi dete."

### Q15. "Future work?"
**Jawab:** "4 cheezein, priority order mein: (1) Saraiki corpus par LoRA fine-tuning (WER target <20%); (2) lesion image classifier (EfficientNet ensemble — literature mein 98%+ reported); (3) Next.js + Leaflet dashboard (GIS surveillance UI); (4) tehsil-level pilot with Layyah livestock office — real SPMS ticket volume par evaluation."

---

## PART 3 — KABHI MAT BOLO (honesty checklist)

- ❌ "Whisper Saraiki support karta hai" — nahi karta. Transfer pipeline ka dawa karo.
- ❌ "Hamari accuracy 98% hai" — tumhare paas 5/5 rule tests hain, clinical validation nahi. MDPI ke 98% **unke** hain, tumhare nahi — cite karo, claim mat karo.
- ❌ "Government ke saath partnership hai" — nahi hai. Independent integration hai.
- ❌ "Image se bimari detect hoti hai" — future work hai, implemented nahi.
- ❌ "Poora Punjab day one" — pilot Layyah hai. Scale roadmap hai, deployment nahi.
- ✅ Har "nahi pata / nahi hai" ka jawab ready rakho — panel imandari ko number deta hai, bluff ko pakarta hai.

---

## PART 4 — 4-DIN KA PLAN (Oct 13 → Oct 17)

- [x] **Oct 13 (aaj):** Walking skeleton + Saraiki wiring + live-call flow + ye research doc — DONE
- [ ] **Oct 14:** Faisla — **Next.js frontend + Leaflet dashboard** YA **defense presentation** (dono mein se ek; waqt ek ka hai)
- [ ] **Oct 15:** Chuni hui cheez complete + demo rehearsal (3 layers — Q5 dekho)
- [ ] **Oct 16:** Q&A rat lo (uper wale 15) + supervisor ko demo dikhao agar mauqa mile
- [ ] **Oct 17:** Defense. Subah Vapi test call kar ke link warm rakho.

**Supervisor wali baat:** unko "harane" ka tareeqa ek hi hai — demo itna smooth aur Q&A itne solid ke panel khud mutmain ho jaye. Ye document usi ka hathiyar hai.

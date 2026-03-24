import json
import os
import re
import unittest
from unittest.mock import MagicMock, patch

from complaint_parsing import (
    _clean_ocr_noise,
    _detect_language,
    _extract_complaint_insights_via_openai,
    _extract_location_fragment,
    _extract_method_fragment,
    _is_plausible_location,
    _normalize_whitespace,
    _resolve_translation_provider_sequence,
    get_translation_config,
    parse_document,
)


CALIBRATION_COMPLAINT_1 = """
Date
12 March 2026
From
Ramesh Kumar, Age 42, residing at House No. 14-2-117, Shivaji Nagar, Hyderabad.
Subject
Complaint regarding theft of cash and gold ornaments from my house

Respected Sir/Madam,
I submit that I am working as a small trader and I live with my family at the above address. On 11 March 2026, at about 7:30 PM, my wife and I locked the house and went to attend a family function in Dilsukhnagar. When we returned at around 10:15 PM, we found the front door latch damaged and the bedroom cupboard open.
On checking the cupboard, we found that cash of about Rs. 85,000, one gold chain, two gold bangles, and one pair of earrings were missing. The room was disturbed and some clothes were thrown on the floor. The neighbours informed us that they had noticed an unknown man moving near our lane around 9:00 PM, but nobody suspected theft at that time.
I request you to register my complaint, inspect the scene, collect CCTV footage from the nearby shops, and take necessary action to trace the offenders and recover the stolen property.
Yours faithfully,
Sd/- Ramesh Kumar
"""

CALIBRATION_COMPLAINT_2 = """
Mobile Phone and Purse Theft Complaint
Date
05 April 2026
From
Sana Begum, Age 29, residing at Flat No. 203, Al Noor Residency, Tolichowki, Hyderabad.
Subject
Complaint regarding theft of mobile phone and purse in city bus

Respected Officer,
Today, on 05 April 2026, I travelled by bus route 127 from Mehdipatnam to Abids at about 9:15 AM for office work. The bus was very crowded. After I got down near GPO, Abids, at around 10:00 AM, I noticed that my handbag zip was partly open.
On checking, I found that my purse containing Aadhaar copy, debit card, office ID card, and cash of about Rs. 4,500 was missing. My mobile phone, a black Samsung Galaxy device with SIM number ending 4432, was also not found in the bag. I immediately called my number from a colleague's phone, but it was switched off.
I suspect that some unknown person stole my belongings during the bus journey. Kindly register this complaint, block or trace the device if possible, and take action against the unknown offender.
Thanking you.
Sd/- Sana Begum
"""

CALIBRATION_COMPLAINT_3 = """
Date
18 January 2026
From
Pradeep Singh, Age 34, residing at H.No. 6-4-88, Chikkadpally, Hyderabad.
Subject
Complaint regarding theft of motorcycle parked outside office

Sir,
I am submitting this complaint regarding theft of my motorcycle. On 17 January 2026, I parked my Hero Splendor Plus, black and red colour, registration number TS09AB4587, outside my office building near RTC Cross Roads at around 10:00 AM.
When I came back at about 6:20 PM, the vehicle was missing from the parking area. I searched nearby streets and asked the watchman and shopkeepers, but nobody could say who took it. One tea stall owner told me that around 2:00 PM he saw two young men standing near the parked vehicles, but he did not pay attention.
The motorcycle had valid insurance and RC documents are available with me. I request you to register a case, verify nearby CCTV cameras, and help in tracing my stolen vehicle.
Sd/- Pradeep Singh
"""

CALIBRATION_COMPLAINT_4 = """
Date
27 February 2026
From
Lakshmi Devi, Age 51, residing at H.No. 2-3-901, Amberpet, Hyderabad.
Subject
Complaint regarding chain snatching by two persons on bike

Respected Sir,
On 26 February 2026, at about 6:45 PM, I was walking back to my house from the vegetable market near Amberpet main road. When I reached the lane near the temple, two unknown persons came from behind on a black motorbike.
The person sitting on the back suddenly pulled the gold chain from my neck and both of them sped away towards Golnaka. Due to the force, I suffered a small scratch on my neck and nearly fell down. The chain was about 22 grams and had sentimental value as it was gifted by my parents.
A few local people came there after hearing my cry, but the offenders had already escaped. I request you to kindly register my complaint and take necessary action to identify and catch the offenders.
Sd/- Lakshmi Devi
"""

CALIBRATION_COMPLAINT_5 = """
Date
From
Subject
09 May 2026
Mohd. Arif, Age 46, residing at Shop No. 8-1-54, Old
Market Lane, Karwan, Hyderabad.
Complaint regarding intentional fire set to my storage
room
Respected Police Officer,
I run a small hardware and paint shop at the above address. On the night of 08 May
2026, at around 11:40 PM, I received a phone call from a nearby tea stall owner informing
me that smoke was coming from the rear side of my shop. I rushed to the spot and found
flames coming out of the storage room used for keeping paint cans, tools, and electrical
goods.
Local people and fire service personnel helped control the fire. However, a large quantity of
goods was damaged. I strongly suspect foul play because for the past two weeks I had a
dispute with a former worker named Imtiyaz regarding unpaid stock shortage allegations,
and he had threatened that I would suffer loss.
I request you to investigate the incident as a case of deliberate fire setting, examine the
scene, and take appropriate legal action.
Sd/- Mohd. Arif
"""

MIXED_TELUGU_OCR_SAMPLE = """
గారికి నమస్కరించి వ్రాయునది.
badgi
Date: 07-11-2025
mm
Inspectos eb police, Attapur ps
Bou thόπο Sardar Jagendar singh sto saevan singh,
Age: 30yrs, DCC: put job, Plo: Gururanak School Backside, Sikhchours,
Altapur ను తమంత మనవి చేయునది ఏమనగా! మేము ముతల్లి
చండులకు ముగ్గురు ఆడ మరియు ముగ్గరం మగ సంతానం కలరు,
το της σωσω Sardar Guruprath singh sto saevan Singh,
Age: 22 yrs, occ: put job, 2000: 04-11-2025 POE Bidares Gururanale
Daavji యొక్క పుట్టినరోజు సందర్భంగాం, అక్కడ భారీగా రాత్రి అవుతుంది అనా
తెలియడంతో, మాం తమ్ముడు, తన సాహనంయైన వెళ్ళినాడు. తరిగి. తేది:
08-11-2025 నాడు సమయం అందాడి 23:00 గంటలకు, మం చిన్న తమ్ముడు
మళ్ళి అనగా తనిత పాటు చాలు మంది అకడి వెళ్ళి తిరిగి వాళ్ళ వా వారు
Received on 07/11/2025 at 0500hes
As per the contents of the above petition, I A Vankabesh megütened a
Case in conto. 945/2025 U/S 109/4) BNS and Investigation Entrusted
to Ch. Sreenu sopser/711125
Dob, Gurudwara, qnumber, dajendranagar jó t
:
వచ్చిసురు. అప్పుడు ము తమ్ముడత Mandeep Singh. తన బండిని.
నిలబడి వున్న తమ్ముడి కాళ్ళపైన ఎక్కించాడు. ద ఎందుకు to woడి,
నపైకి వింద్రన్నావ్? అని అడిగినందున, అతను ఛుంకుమంటలు పట్టడం
చేసూడు. ఇది చిన్న సంఘటన Sanga Reddys అయింది. తరుమిత
అక్కడ
నుండి. వచ్చేశరు. అయితే అట్టి విషషముని మనసుత పెట్టుకొని
Ouridicara parking. (9number) wgo κοβεί μυ
20
Whs Botas mardeep Singh, Jaspreeth Singh, Boby singh, Vicky sing,
Rhku sirghew Caliber Singh 8000 800
Helly Guruprabh Singh Tue 206. talewareG 2 Bro
Attapur Police Stati.
So చిన్న తమ్ముడుకి
తలు, ఎడలు చెయీపి మరిపియు కుడి
1845
Sub-Inspector of Police
Cyberabada
రక్తగాయము అయ్యింది. oops ounanda hospital Bee వెళ్ళనుమం
విట్టిన మం చినతమ్ముడిపై దాడి చేసిన వ్యంలపై చర్యలు ఆలకోగలరు
Ro
Jagerdas Singh
"""

CALIBRATION_ROAD_ACCIDENT = """
Statement of Chinthanippu Hemanth Choudhary S/O Ch. Venkateswarrao
Age 22 years, Private Job, R/O 1-4-1022/20/2 Harinagar Main Road, Ramnagar
Phone: 7989340875
Statement Recorded by PS Warasiguda on 07-02-2026 at 10:50 AM
3rd floor Room no 315 Srikara Hospital RTC X Road
MLC NO 2124

I, Ch. Hemanth Choudhary S/O Ch. Venkateswarrao, Age 22, have been living for the past 22 years at the above-mentioned address along with my mother, younger sister, and grandmother. Date: 06-02-2026, time around 11:00 PM, when I was returning from office to home, when I was coming from Moram X Road to Parsigutta, in the middle of the route, a bike coming from the opposite direction, while overtaking another vehicle, hit me. I fell down and for some time I did not remember anything. A person nearby immediately called my mother on the phone. Meanwhile, when a call was made to the ambulance, the ambulance came. In the meantime, my mother also came. Immediately they brought me to Srikara Hospital, RTC X Road. At present I am receiving treatment. The doctors informed me that the bones in my right leg below the knee are broken in two places. At present they told me that an operation should be done. At present my health is stable. On this incident, you may take legal action and give me appropriate justice.
"""

TRANSLATED_STATEMENT_SAMPLE = """
Statement of Chinthanippu Hemanth Choudhary S/O Ch. -Swar rao
Trao
Age 22 years OCL private Job Kajem pee food, PVT,
OCL
Medichel R/O 1-4-1022/20/2 Harimagas mein Road Janistan perr
Rammagar ph 7989340875 Stet ment Recorded by pe 5085
B. Ranesh ps.
warasiguda
-02-2026 at 10:50 AM
on 07-02-
3rd floor Rom no 315 Srikara hospital RTC.X Road
MLC NO 2124 IP NO: 022544/23010368
1
Stetd 154.

I, Ch. Hemanth Choudhary S/O Ch. Venkateswarbac, Age 22, have been living for the past 22 years at the above-mentioned address along with my mother, younger sister, and grandmother. Date: 06-02-2026, time around 11:00 pm, when I was returning from office to home, when I was coming from Moram ond X Roంగి to Parsipatta, in the middle of the route, a bike coming opposite me, while overtaking another vehicle, hit me. I fell down and for some time I did not remember anything. A person nearby immediately called my mother on the phone. Meanwhile, when a call was made to the ambulance, the ambulance came. In the meantime, my mother also came. Immediately they brought me to Srikara Hospital, RTC X Road. At present I am taking treatment. The doctors informed me that the bones in my right leg below the knee are broken in two places. At present they told me that an operation should be done. At present my health is stable. On this incident, you may take legal action and give me appropriate justice.

Hemanth

Received on 07/02/26 at 1:00 hr.
Made petition contery & entrusted
to se
Ramchandera Reddy for
ch Hemouth
enquiry & export. Reopl
on 07/02/26 at 12:80 hr.
07/02/26
a in
a case in
After enquiry registered
CrAN: 2,3/ 2026 Uls
125
(9) BNS and
contrusted to se
Ramchander
Reddy
per investigation. Reepy 26
ph 7989340875
"""


class ComplaintParsingTests(unittest.TestCase):
    def setUp(self) -> None:
        self._saved_env = {
            key: os.environ.get(key)
            for key in (
                "TRANSLATION_ENABLED",
                "TRANSLATION_PROVIDER",
                "TRANSLATION_FALLBACK_PROVIDER",
                "TRANSLATION_PROJECT_ID",
                "TRANSLATION_LOCATION",
                "TRANSLATION_TARGET_LANGUAGE",
                "OPENAI_TRANSLATION_ENABLED",
                "OPENAI_TRANSLATION_MODEL",
                "OPENAI_TRANSLATION_REASONING_EFFORT",
                "OPENAI_TRANSLATION_API_KEY",
                "OPENAI_EXTRACTION_ENABLED",
                "OPENAI_EXTRACTION_MODEL",
                "OPENAI_EXTRACTION_REASONING_EFFORT",
                "OPENAI_EXTRACTION_MIN_CONFIDENCE",
                "OPENAI_EXTRACTION_REQUIRE_EVIDENCE",
                "OPENAI_API_KEY",
                "DOC_AI_PROJECT_ID",
                "GEMINI_API_KEY",
                "GEMINI_TRANSLATION_ENABLED",
                "GEMINI_TRANSLATION_MODEL",
                "GEMINI_BASE_URL",
                "TRANSLATION_QE_ENABLED",
                "TRANSLATION_QE_THRESHOLD",
            )
        }
        os.environ["OPENAI_EXTRACTION_ENABLED"] = "false"
        os.environ["OPENAI_EXTRACTION_MIN_CONFIDENCE"] = "medium"
        os.environ["OPENAI_EXTRACTION_REQUIRE_EVIDENCE"] = "true"

    def tearDown(self) -> None:
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_extracts_complete_english_complaint(self) -> None:
        sample = """
        Subject: Complaint regarding theft of mobile phone
        My name is Ram Kumar.
        I want to report that my mobile phone was stolen on 15 March 2026 at around 8 PM near XYZ Market bus stand.
        The unknown accused took the phone from my pocket in a crowded bus.
        The theft appears to be opportunistic.
        """

        result = parse_document(sample)

        self.assertEqual(result["document_type"], "police_complaint")
        self.assertEqual(result["language"]["detected"], "en")
        self.assertEqual(result["language"]["translation_status"], "not_needed")
        self.assertEqual(result["complaint"]["who"]["status"], "present")
        self.assertEqual(result["complaint"]["what"]["status"], "present")
        self.assertEqual(result["complaint"]["when"]["status"], "present")
        self.assertEqual(result["complaint"]["where"]["status"], "present")
        self.assertEqual(result["complaint"]["why"]["status"], "present")
        self.assertEqual(result["complaint"]["how"]["status"], "present")
        self.assertEqual(result["gaps"]["missing_fields"], [])
        self.assertFalse(result["gaps"]["requires_review"])
        self.assertTrue(result["summary"]["complaint_brief"])
        self.assertEqual(result["summary"]["review_questions"], [])
        self.assertEqual(result["meta"]["extraction"]["strategy"], "heuristic_only")

    def test_detects_hindi_and_flags_translation_gap_when_disabled(self) -> None:
        os.environ["TRANSLATION_ENABLED"] = "false"
        sample = (
            "मेरी शिकायत यह है कि मेरा मोबाइल 15/03/2026 को शाम 8 बजे बस स्टैंड के पास चोरी हो गया। "
            "अज्ञात आरोपी ने भीड़ वाली बस में मेरी जेब से मोबाइल निकाला।"
        )

        result = parse_document(sample)

        self.assertEqual(result["language"]["detected"], "hi")
        self.assertEqual(result["language"]["translation_status"], "disabled")
        self.assertIn("translation_to_english_unavailable", result["gaps"]["pipeline_flags"])
        self.assertTrue(result["gaps"]["requires_review"])

    def test_detects_telugu_when_ocr_noise_almost_matches_english_character_count(self) -> None:
        language = _detect_language(MIXED_TELUGU_OCR_SAMPLE)

        self.assertEqual(language["language_code"], "te")
        self.assertEqual(language["counts"]["te"], 612)
        self.assertEqual(language["counts"]["en"], 617)

    @patch("complaint_parsing._translate_to_english_via_openai")
    @patch("complaint_parsing._translate_to_english_via_google")
    def test_falls_back_to_openai_translation_when_google_fails(
        self,
        google_translate_mock,
        openai_translate_mock,
    ) -> None:
        os.environ["TRANSLATION_ENABLED"] = "true"
        os.environ["TRANSLATION_PROVIDER"] = "auto"
        os.environ["TRANSLATION_FALLBACK_PROVIDER"] = "openai"
        os.environ["TRANSLATION_PROJECT_ID"] = "wealth-report"
        os.environ["OPENAI_API_KEY"] = "test-key"
        os.environ["OPENAI_TRANSLATION_MODEL"] = "gpt-5.2"

        google_translate_mock.return_value = {
            "english_text": "मूल हिंदी पाठ",
            "source_language": "hi",
            "target_language": "en",
            "status": "failed",
            "provider": "google_cloud_translate",
            "model": None,
            "error": "Cloud Translation API disabled.",
        }
        openai_translate_mock.return_value = {
            "english_text": (
                "My name is Ram Kumar. My mobile phone was stolen on 15 March 2026 at around 8 PM "
                "near XYZ Market bus stand. An unknown person took it from my pocket in a crowded bus."
            ),
            "source_language": "hi",
            "target_language": "en",
            "status": "translated",
            "provider": "openai_responses",
            "model": "gpt-5.2",
            "error": None,
        }

        result = parse_document(
            "मेरा नाम राम कुमार है। मेरा मोबाइल 15 मार्च 2026 को रात 8 बजे XYZ मार्केट बस स्टैंड के पास चोरी हो गया।"
        )

        self.assertEqual(result["language"]["detected"], "hi")
        self.assertEqual(result["language"]["translation_status"], "translated")
        self.assertEqual(result["language"]["translation_provider"], "openai_responses")
        self.assertEqual(result["language"]["translation_model"], "gpt-5.2")
        self.assertEqual(result["complaint"]["who"]["status"], "present")
        self.assertEqual(result["complaint"]["what"]["status"], "present")
        self.assertEqual(result["complaint"]["when"]["status"], "present")
        self.assertEqual(result["complaint"]["where"]["status"], "present")
        self.assertEqual(result["complaint"]["how"]["status"], "present")
        self.assertEqual(google_translate_mock.call_count, 1)
        self.assertEqual(openai_translate_mock.call_count, 1)

    @patch("complaint_parsing._translate_to_english_via_openai")
    @patch("complaint_parsing._translate_to_english_via_google")
    def test_translates_mixed_telugu_ocr_when_telugu_script_is_substantial(
        self,
        google_translate_mock,
        openai_translate_mock,
    ) -> None:
        os.environ["TRANSLATION_ENABLED"] = "true"
        os.environ["TRANSLATION_PROVIDER"] = "auto"
        os.environ["TRANSLATION_FALLBACK_PROVIDER"] = "openai"
        os.environ["TRANSLATION_PROJECT_ID"] = "wealth-report"

        google_translate_mock.return_value = {
            "english_text": (
                "I respectfully submit this petition. My younger brother Mandeep Singh was attacked "
                "near Gurudwara parking at around 23:00 hours and suffered bleeding injuries."
            ),
            "source_language": "te",
            "target_language": "en",
            "status": "translated",
            "provider": "google_cloud_translate",
            "model": None,
            "error": None,
        }
        openai_translate_mock.return_value = {
            "english_text": "",
            "source_language": "te",
            "target_language": "en",
            "status": "unavailable",
            "provider": "openai_responses",
            "model": None,
            "error": "Should not be called when Google succeeds.",
        }

        result = parse_document(MIXED_TELUGU_OCR_SAMPLE)

        self.assertEqual(result["language"]["detected"], "te")
        self.assertEqual(result["language"]["translation_status"], "translated")
        self.assertEqual(result["language"]["translation_provider"], "google_cloud_translate")
        self.assertEqual(result["text"]["english_text"], google_translate_mock.return_value["english_text"])
        self.assertEqual(google_translate_mock.call_count, 1)
        self.assertEqual(openai_translate_mock.call_count, 0)

    def test_extracts_complainant_and_victim_from_translated_statement_style_text(self) -> None:
        result = parse_document(TRANSLATED_STATEMENT_SAMPLE)
        who = result["complaint"]["who"]["components"]

        self.assertEqual(result["language"]["detected"], "en")
        self.assertEqual(result["language"]["translation_status"], "not_needed")
        self.assertEqual(who["complainant"]["status"], "present")
        self.assertIn("Ch. Hemanth Choudhary", who["complainant"]["values"])
        self.assertEqual(who["victim"]["status"], "uncertain")
        self.assertIn("Ch. Hemanth Choudhary", who["victim"]["values"])
        self.assertTrue(result["summary"]["complaint_brief"])
        self.assertIsInstance(result["summary"]["review_questions"], list)

    @patch("complaint_parsing._extract_complaint_insights_via_openai")
    def test_question_guided_extraction_enriches_summary_and_fields_with_validation(self, extraction_mock) -> None:
        extraction_mock.return_value = {
            "complaint_summary": (
                "Ch. Hemanth Choudhary states that he was hit by an oncoming bike near RTC X Road "
                "on 06-02-2026 around 11:00 PM and suffered fractures in his right leg."
            ),
            "review_questions": [
                "Who was riding the bike that hit him",
                "Where on the route did the collision occur exactly?",
            ],
            "answers": {
                "who": {
                    "complainant": ["Ch. Hemanth Choudhary"],
                    "victim": ["Ch. Hemanth Choudhary"],
                    "accused": ["Unknown bike rider"],
                    "witnesses": ["Nearby caller"],
                    "confidence": "medium",
                    "evidence": ["A person nearby immediately called my mother on the phone."],
                },
                "what": {
                    "answer": "Road accident complaint after a bike hit the complainant while overtaking another vehicle",
                    "confidence": "high",
                    "evidence": ["a bike coming opposite me, while overtaking another vehicle, hit me"],
                },
                "when": {
                    "answer": "06-02-2026 around 11:00 PM",
                    "date": "06-02-2026",
                    "time": "11:00 PM",
                    "confidence": "high",
                    "evidence": ["Date: 06-02-2026, time around 11:00 pm"],
                },
                "where": {
                    "answer": "On the route near RTC X Road while returning home",
                    "confidence": "medium",
                    "evidence": ["they brought me to Srikara Hospital, RTC X Road"],
                },
                "why": {
                    "answer": "",
                    "confidence": "low",
                    "evidence": [],
                },
                "how": {
                    "answer": "A bike coming from the opposite side hit him while overtaking another vehicle",
                    "confidence": "high",
                    "evidence": ["a bike coming opposite me, while overtaking another vehicle, hit me"],
                },
            },
        }

        result = parse_document(TRANSLATED_STATEMENT_SAMPLE)

        self.assertIn("Ch. Hemanth Choudhary", result["summary"]["complaint_brief"])
        self.assertIn("06-02-2026", result["summary"]["complaint_brief"])
        self.assertIn(
            "Who was riding the bike that hit him?",
            result["summary"]["review_questions"],
        )
        self.assertEqual(
            result["complaint"]["where"]["value"],
            "On the route near RTC X Road while returning home",
        )
        self.assertIn(
            "Unknown bike rider",
            result["complaint"]["who"]["components"]["accused"]["values"],
        )
        self.assertTrue(result["meta"]["extraction"]["question_guided_applied"])
        self.assertTrue(result["meta"]["extraction"]["question_guided_response_received"])
        self.assertIn(
            "where",
            result["meta"]["extraction"]["question_guided_validation"]["accepted_fields"],
        )
        self.assertEqual(
            result["summary"]["extraction_strategy"],
            "heuristic_plus_question_guided",
        )

    @patch("complaint_parsing._extract_complaint_insights_via_openai")
    def test_question_guided_extraction_rejects_low_confidence_override(self, extraction_mock) -> None:
        extraction_mock.return_value = {
            "review_questions": ["Where did the collision occur exactly?"],
            "answers": {
                "where": {
                    "answer": "Inside Srikara Hospital, RTC X Road",
                    "confidence": "low",
                    "evidence": ["they brought me to Srikara Hospital, RTC X Road"],
                }
            },
        }

        result = parse_document(TRANSLATED_STATEMENT_SAMPLE)

        self.assertNotEqual(
            result["complaint"]["where"]["value"],
            "Inside Srikara Hospital, RTC X Road",
        )
        self.assertFalse(result["meta"]["extraction"]["question_guided_applied"])
        self.assertEqual(
            result["meta"]["extraction"]["question_guided_validation"]["rejected_reasons"]["where"],
            "confidence_below_threshold",
        )

    @patch("complaint_parsing._extract_complaint_insights_via_openai")
    def test_question_guided_extraction_requires_source_evidence(self, extraction_mock) -> None:
        extraction_mock.return_value = {
            "review_questions": ["Who exactly saw the accident happen?"],
            "answers": {
                "who": {
                    "complainant": ["Ch. Hemanth Choudhary"],
                    "victim": ["Ch. Hemanth Choudhary"],
                    "accused": ["Unknown bike rider"],
                    "witnesses": ["Traffic constable"],
                    "confidence": "high",
                    "evidence": ["Witness statement recorded separately"],
                }
            },
        }

        result = parse_document(TRANSLATED_STATEMENT_SAMPLE)

        self.assertEqual(
            result["complaint"]["who"]["components"]["accused"]["status"],
            "missing",
        )
        self.assertEqual(
            result["meta"]["extraction"]["question_guided_validation"]["rejected_reasons"]["who"],
            "evidence_not_found_in_source",
        )

    def test_builds_fallback_review_questions_when_key_fields_are_missing(self) -> None:
        result = parse_document("Subject: Complaint regarding theft")

        self.assertTrue(result["summary"]["complaint_brief"])
        self.assertIn(
            "Who are the complainant, victim, accused, and witnesses in this complaint?",
            result["summary"]["review_questions"],
        )
        self.assertIn(
            "Where did the incident occur?",
            result["summary"]["review_questions"],
        )

    def test_calibration_samples_map_to_cleaner_5w1h_outputs(self) -> None:
        samples = [
            {
                "text": CALIBRATION_COMPLAINT_1,
                "complainant": "Ramesh Kumar",
                "accused": "Unknown person",
                "what": "Complaint regarding theft of cash and gold ornaments from my house",
                "when_date": "11 March 2026",
                "where_contains_any": ["shivaji nagar", "house no. 14-2-117", "our lane"],
                "why_status": "missing",
                "how_contains": "front door latch damaged",
            },
            {
                "text": CALIBRATION_COMPLAINT_2,
                "complainant": "Sana Begum",
                "accused": "Unknown person",
                "what": "Complaint regarding theft of mobile phone and purse in city bus",
                "when_date": "05 April 2026",
                "where_contains_any": ["city bus", "abids", "gpo"],
                "why_status": "missing",
                "how_contains": "crowded city bus journey",
            },
            {
                "text": CALIBRATION_COMPLAINT_3,
                "complainant": "Pradeep Singh",
                "accused": None,
                "what": "Complaint regarding theft of motorcycle parked outside office",
                "when_date": "17 January 2026",
                "where_contains_any": ["office", "rtc cross roads", "parking area"],
                "why_status": "missing",
                "how_contains": "parking area",
            },
            {
                "text": CALIBRATION_COMPLAINT_4,
                "complainant": "Lakshmi Devi",
                "accused": "Unknown person",
                "what": "Complaint regarding chain snatching by two persons on bike",
                "when_date": "26 February 2026",
                "where_contains_any": ["amberpet", "temple"],
                "why_status": "missing",
                "how_contains": "pulled the gold chain",
            },
            {
                "text": CALIBRATION_COMPLAINT_5,
                "complainant": "Mohd. Arif",
                "accused": "Imtiyaz",
                "what": "Complaint regarding intentional fire set to my storage room",
                "when_date": "08 May 2026",
                "where_contains_any": ["karwan", "old market lane"],
                "why_status": "present",
                "how_contains": "deliberate fire setting",
            },
        ]

        for sample in samples:
            with self.subTest(complainant=sample["complainant"]):
                result = parse_document(sample["text"])
                complaint = result["complaint"]
                who = complaint["who"]["components"]

                self.assertEqual(result["document_type"], "police_complaint")
                self.assertEqual(result["language"]["detected"], "en")
                self.assertEqual(result["language"]["translation_status"], "not_needed")
                self.assertEqual(complaint["what"]["status"], "present")
                self.assertEqual(complaint["when"]["status"], "present")
                self.assertEqual(complaint["where"]["status"], "present")
                self.assertEqual(complaint["how"]["status"], "present")
                self.assertEqual(complaint["why"]["status"], sample["why_status"])

                self.assertIn(sample["complainant"], who["complainant"]["values"])
                self.assertIn(sample["complainant"], who["victim"]["values"])
                if sample["accused"]:
                    self.assertIn(sample["accused"], who["accused"]["values"])
                else:
                    self.assertEqual(who["accused"]["status"], "missing")

                self.assertEqual(complaint["what"]["value"], sample["what"])
                self.assertIn(sample["when_date"], complaint["when"]["value"])
                self.assertTrue(
                    any(
                        fragment.lower() in complaint["where"]["value"].lower()
                        for fragment in sample["where_contains_any"]
                    )
                )
                self.assertIn(sample["how_contains"].lower(), complaint["how"]["value"].lower())

        fire_result = parse_document(CALIBRATION_COMPLAINT_5)
        self.assertIn("dispute", fire_result["complaint"]["why"]["value"].lower())
        self.assertIn("threatened", fire_result["complaint"]["why"]["value"].lower())

    def test_road_accident_heuristic_extraction_captures_key_fields(self) -> None:
        result = parse_document(CALIBRATION_ROAD_ACCIDENT)
        complaint = result["complaint"]
        who = complaint["who"]["components"]

        self.assertEqual(result["document_type"], "police_complaint")
        self.assertEqual(result["language"]["detected"], "en")
        self.assertEqual(who["complainant"]["status"], "present")
        self.assertIn("Ch. Hemanth Choudhary", who["complainant"]["values"])

        where_value = (complaint["where"]["value"] or "").lower()
        self.assertNotIn(
            "hospital", where_value,
            "WHERE should not contain hospital location",
        )
        self.assertNotIn(
            "receiving treatment", where_value,
            "WHERE should not contain treatment location",
        )

        self.assertIn("06-02-2026", complaint["when"]["value"])
        self.assertEqual(complaint["how"]["status"], "present")

        where_value = complaint["where"]["value"] or ""
        self.assertTrue(
            re.search(r"(?i)moram|parsigutta|route", where_value),
            f"WHERE should contain route text, got: {where_value!r}",
        )

        how_value = complaint["how"]["value"] or ""
        self.assertNotIn(
            "Date:", how_value,
            "HOW should not contain date/time preamble",
        )

    @patch("complaint_parsing._extract_complaint_insights_via_openai")
    def test_road_accident_question_guided_extraction_produces_correct_fields(
        self, extraction_mock
    ) -> None:
        extraction_mock.return_value = {
            "complaint_summary": (
                "Road accident where an oncoming bike hit the complainant while "
                "overtaking another vehicle, causing leg fractures"
            ),
            "review_questions": [
                "Who was riding the bike that hit the complainant?",
                "Exact location on the route where the collision occurred?",
            ],
            "answers": {
                "who": {
                    "complainant": ["Ch. Hemanth Choudhary"],
                    "victim": ["Ch. Hemanth Choudhary"],
                    "accused": ["Unknown bike rider"],
                    "witnesses": ["Nearby person who called mother"],
                    "confidence": "medium",
                    "evidence": [
                        "a bike coming from the opposite direction",
                        "A person nearby immediately called my mother",
                    ],
                },
                "what": {
                    "answer": (
                        "Road accident where an oncoming bike hit the complainant "
                        "while overtaking another vehicle, causing leg fractures"
                    ),
                    "confidence": "high",
                    "evidence": [
                        "a bike coming from the opposite direction, while overtaking "
                        "another vehicle, hit me"
                    ],
                },
                "when": {
                    "answer": "06-02-2026 around 11:00 PM",
                    "date": "06-02-2026",
                    "time": "11:00 PM",
                    "confidence": "high",
                    "evidence": ["Date: 06-02-2026, time around 11:00 PM"],
                },
                "where": {
                    "answer": "On the route from Moram X Road to Parsigutta",
                    "confidence": "medium",
                    "evidence": [
                        "when I was coming from Moram X Road to Parsigutta"
                    ],
                },
                "why": {
                    "answer": (
                        "Reckless driving — bike rider overtook from opposite "
                        "direction into oncoming traffic"
                    ),
                    "confidence": "high",
                    "evidence": [
                        "a bike coming from the opposite direction, while "
                        "overtaking another vehicle, hit me"
                    ],
                },
                "how": {
                    "answer": (
                        "A bike coming from the opposite direction overtook "
                        "another vehicle and collided head-on with the complainant"
                    ),
                    "confidence": "high",
                    "evidence": [
                        "a bike coming from the opposite direction, while "
                        "overtaking another vehicle, hit me. I fell down"
                    ],
                },
            },
        }

        result = parse_document(CALIBRATION_ROAD_ACCIDENT)
        complaint = result["complaint"]

        self.assertIn("Road accident", complaint["what"]["value"])
        self.assertIn(
            "Moram X Road",
            complaint["where"]["value"],
        )
        self.assertIn("reckless", complaint["why"]["value"].lower())
        self.assertIn("overtook", complaint["how"]["value"].lower())
        self.assertIn(
            "Unknown bike rider",
            complaint["who"]["components"]["accused"]["values"],
        )
        self.assertTrue(result["meta"]["extraction"]["question_guided_applied"])

    def test_builds_telangana_fir_draft_for_road_accident(self) -> None:
        result = parse_document(CALIBRATION_ROAD_ACCIDENT)
        fir_draft = result["fir_draft"]
        sections = [item["section"] for item in fir_draft["proposed_bns_sections"]]

        self.assertEqual(fir_draft["status"], "draft_for_police_review")
        self.assertEqual(fir_draft["format"], "telangana_iif1_style")
        self.assertEqual(fir_draft["jurisdiction"]["state"], "Telangana")
        self.assertEqual(fir_draft["jurisdiction"]["police_station"], "Warasiguda")
        self.assertEqual(fir_draft["informant"]["name"], "Ch. Hemanth Choudhary")
        self.assertIn("281", sections)
        self.assertIn("125(b)", sections)
        self.assertIn("TELANGANA POLICE - DRAFT FIRST INFORMATION REPORT", fir_draft["formatted_text"])
        self.assertIn("BNS 281", fir_draft["formatted_text"])

    def test_builds_fir_draft_with_specific_sections_for_house_theft(self) -> None:
        result = parse_document(CALIBRATION_COMPLAINT_1)
        fir_draft = result["fir_draft"]
        sections = [item["section"] for item in fir_draft["proposed_bns_sections"]]

        self.assertEqual(fir_draft["occurrence"]["nature_of_offence"], "Aggravated theft")
        self.assertEqual(fir_draft["informant"]["name"], "Ramesh Kumar")
        self.assertIn("305", sections)
        self.assertIn("331", sections)
        self.assertIn("cash and gold ornaments", (fir_draft["case_profile"]["property_or_loss"] or "").lower())

    def test_builds_fir_draft_with_cheating_sections_for_cyber_fraud(self) -> None:
        sample = """
        I, Sunita Reddy, received a phone call on 10-03-2026 from someone claiming to be an SBI bank officer.
        He said my account would be blocked unless I verified my details. He asked me to share the OTP sent to my phone.
        After I shared the OTP, Rs. 1,50,000 was debited from my savings account. I realized I was cheated and went to the bank.
        """

        result = parse_document(sample)
        fir_draft = result["fir_draft"]
        sections = [item["section"] for item in fir_draft["proposed_bns_sections"]]

        self.assertEqual(fir_draft["informant"]["name"], "Sunita Reddy")
        self.assertIn("318(4)", sections)
        self.assertIn("319", sections)
        self.assertIn("Unknown caller", fir_draft["parties"]["accused"])
        self.assertIn("1,50,000", fir_draft["formatted_text"])

    def test_is_plausible_location_rejects_time_values(self) -> None:
        for value in ("1:00 hr", "12:80hr", "10:50 AM", "12:08hrs"):
            self.assertFalse(
                _is_plausible_location(value),
                f"Time-like value should be rejected: {value!r}",
            )

    def test_extract_method_fragment_matches_road_accident(self) -> None:
        sentence = (
            "a bike coming from the opposite direction, "
            "while overtaking another vehicle, hit me"
        )
        fragment = _extract_method_fragment(sentence)
        self.assertIsNotNone(fragment, "Should extract a method fragment for road accident")
        self.assertIn("hit", fragment.lower())

    def test_extract_location_fragment_matches_route(self) -> None:
        sentence = (
            "when I was coming from Moram X Road to Parsigutta, "
            "in the middle of the route"
        )
        fragment = _extract_location_fragment(sentence)
        self.assertIsNotNone(fragment, "Should extract route location")
        self.assertIn("Moram", fragment)
        self.assertIn("Parsigutta", fragment)


    def test_clean_ocr_noise_removes_greek_characters(self) -> None:
        text = "Bou thόπο Sardar Jagendar singh"
        cleaned = _clean_ocr_noise(text, "te")
        self.assertNotIn("ό", cleaned)
        self.assertNotIn("π", cleaned)
        self.assertIn("Sardar", cleaned)
        self.assertIn("Jagendar", cleaned)

    def test_clean_ocr_noise_preserves_long_english_words(self) -> None:
        text = "తెలుగు Police Station తెలుగు"
        cleaned = _clean_ocr_noise(text, "te")
        self.assertIn("Police", cleaned)
        self.assertIn("Station", cleaned)

    def test_clean_ocr_noise_nfkc_normalization(self) -> None:
        # ﬁ (U+FB01 fi ligature) should normalize to "fi"
        text = "the ofﬁce building"
        cleaned = _clean_ocr_noise(text, "en")
        self.assertIn("office", cleaned)

    def test_clean_ocr_noise_collapses_excessive_punctuation(self) -> None:
        text = "something happened....... and then"
        cleaned = _clean_ocr_noise(text, "en")
        self.assertNotIn(".......", cleaned)
        self.assertIn("...", cleaned)

    def test_provider_sequence_includes_gemini(self) -> None:
        os.environ["TRANSLATION_PROVIDER"] = "gemini"
        os.environ["TRANSLATION_FALLBACK_PROVIDER"] = "openai"
        config = get_translation_config()
        sequence = _resolve_translation_provider_sequence(config)
        self.assertEqual(sequence, ["gemini", "openai"])

    def test_provider_sequence_gemini_as_fallback(self) -> None:
        os.environ["TRANSLATION_PROVIDER"] = "google"
        os.environ["TRANSLATION_FALLBACK_PROVIDER"] = "gemini"
        os.environ["TRANSLATION_PROJECT_ID"] = "test-project"
        config = get_translation_config()
        sequence = _resolve_translation_provider_sequence(config)
        self.assertEqual(sequence, ["google", "gemini"])

    @patch("complaint_parsing._translate_to_english_via_gemini")
    @patch("complaint_parsing._translate_to_english_via_google")
    def test_falls_back_to_gemini_when_google_fails(
        self,
        google_translate_mock,
        gemini_translate_mock,
    ) -> None:
        os.environ["TRANSLATION_ENABLED"] = "true"
        os.environ["TRANSLATION_PROVIDER"] = "google"
        os.environ["TRANSLATION_FALLBACK_PROVIDER"] = "gemini"
        os.environ["TRANSLATION_PROJECT_ID"] = "test-project"
        os.environ["GEMINI_API_KEY"] = "test-key"
        os.environ["TRANSLATION_QE_ENABLED"] = "false"

        google_translate_mock.return_value = {
            "english_text": "",
            "source_language": "te",
            "target_language": "en",
            "status": "failed",
            "provider": "google_cloud_translate",
            "model": None,
            "error": "Cloud Translation API disabled.",
        }
        gemini_translate_mock.return_value = {
            "english_text": (
                "I respectfully submit this petition regarding the attack on my brother."
            ),
            "source_language": "te",
            "target_language": "en",
            "status": "translated",
            "provider": "gemini",
            "model": "gemini-2.5-flash",
            "error": None,
        }

        result = parse_document(MIXED_TELUGU_OCR_SAMPLE)

        self.assertEqual(result["language"]["detected"], "te")
        self.assertEqual(result["language"]["translation_status"], "translated")
        self.assertEqual(result["language"]["translation_provider"], "gemini")
        self.assertEqual(google_translate_mock.call_count, 1)
        self.assertEqual(gemini_translate_mock.call_count, 1)

    @patch("complaint_parsing._estimate_translation_quality")
    @patch("complaint_parsing._translate_to_english_via_openai")
    @patch("complaint_parsing._translate_to_english_via_google")
    def test_quality_gated_retry_rejects_low_quality_and_accepts_next(
        self,
        google_translate_mock,
        openai_translate_mock,
        qe_mock,
    ) -> None:
        os.environ["TRANSLATION_ENABLED"] = "true"
        os.environ["TRANSLATION_PROVIDER"] = "auto"
        os.environ["TRANSLATION_FALLBACK_PROVIDER"] = "openai"
        os.environ["TRANSLATION_PROJECT_ID"] = "test-project"
        os.environ["OPENAI_API_KEY"] = "test-key"
        os.environ["TRANSLATION_QE_ENABLED"] = "true"
        os.environ["TRANSLATION_QE_THRESHOLD"] = "0.7"

        google_translate_mock.return_value = {
            "english_text": "Bad garbled translation with many errors",
            "source_language": "hi",
            "target_language": "en",
            "status": "translated",
            "provider": "google_cloud_translate",
            "model": None,
            "error": None,
        }
        openai_translate_mock.return_value = {
            "english_text": (
                "My name is Ram Kumar. My mobile phone was stolen on 15 March 2026."
            ),
            "source_language": "hi",
            "target_language": "en",
            "status": "translated",
            "provider": "openai_responses",
            "model": "gpt-5.2",
            "error": None,
        }
        qe_mock.side_effect = [
            {
                "score": 0.3,
                "acceptable": False,
                "method": "gemini_llm_judge",
                "details": "Poor translation quality",
                "error": None,
            },
            {
                "score": 0.85,
                "acceptable": True,
                "method": "gemini_llm_judge",
                "details": "Good translation quality",
                "error": None,
            },
        ]

        result = parse_document(
            "मेरा नाम राम कुमार है। मेरा मोबाइल 15 मार्च 2026 को चोरी हो गया।"
        )

        self.assertEqual(result["language"]["translation_status"], "translated")
        self.assertEqual(result["language"]["translation_provider"], "openai_responses")
        self.assertEqual(result["language"]["translation_quality_score"], 0.85)
        self.assertTrue(result["language"]["translation_quality_acceptable"])
        self.assertFalse(result["language"]["translation_flagged_for_review"])
        self.assertEqual(google_translate_mock.call_count, 1)
        self.assertEqual(openai_translate_mock.call_count, 1)
        self.assertEqual(qe_mock.call_count, 2)

    @patch("complaint_parsing._estimate_translation_quality")
    @patch("complaint_parsing._translate_to_english_via_openai")
    @patch("complaint_parsing._translate_to_english_via_google")
    def test_quality_gated_returns_best_flagged_when_all_below_threshold(
        self,
        google_translate_mock,
        openai_translate_mock,
        qe_mock,
    ) -> None:
        os.environ["TRANSLATION_ENABLED"] = "true"
        os.environ["TRANSLATION_PROVIDER"] = "auto"
        os.environ["TRANSLATION_FALLBACK_PROVIDER"] = "openai"
        os.environ["TRANSLATION_PROJECT_ID"] = "test-project"
        os.environ["OPENAI_API_KEY"] = "test-key"
        os.environ["TRANSLATION_QE_ENABLED"] = "true"
        os.environ["TRANSLATION_QE_THRESHOLD"] = "0.7"

        google_translate_mock.return_value = {
            "english_text": "Low quality google translation",
            "source_language": "hi",
            "target_language": "en",
            "status": "translated",
            "provider": "google_cloud_translate",
            "model": None,
            "error": None,
        }
        openai_translate_mock.return_value = {
            "english_text": "Slightly better openai translation",
            "source_language": "hi",
            "target_language": "en",
            "status": "translated",
            "provider": "openai_responses",
            "model": "gpt-5.2",
            "error": None,
        }
        qe_mock.side_effect = [
            {
                "score": 0.3,
                "acceptable": False,
                "method": "gemini_llm_judge",
                "details": "Poor",
                "error": None,
            },
            {
                "score": 0.5,
                "acceptable": False,
                "method": "gemini_llm_judge",
                "details": "Mediocre",
                "error": None,
            },
        ]

        result = parse_document(
            "मेरा नाम राम कुमार है। मेरा मोबाइल चोरी हो गया।"
        )

        self.assertEqual(result["language"]["translation_status"], "translated")
        # Best result should be from OpenAI (score 0.5 > 0.3)
        self.assertEqual(result["language"]["translation_provider"], "openai_responses")
        self.assertTrue(result["language"]["translation_flagged_for_review"])
        self.assertIn("translation_quality_low", result["gaps"]["pipeline_flags"])


    @patch("complaint_parsing._estimate_translation_quality")
    @patch("complaint_parsing._translate_to_english_via_openai")
    @patch("complaint_parsing._translate_to_english_via_google")
    def test_ensemble_picks_highest_quality_translation(
        self,
        google_translate_mock,
        openai_translate_mock,
        qe_mock,
    ) -> None:
        """With QE + 2 providers, ensemble runs both in parallel and picks highest score."""
        os.environ["TRANSLATION_ENABLED"] = "true"
        os.environ["TRANSLATION_PROVIDER"] = "auto"
        os.environ["TRANSLATION_FALLBACK_PROVIDER"] = "openai"
        os.environ["TRANSLATION_PROJECT_ID"] = "test-project"
        os.environ["OPENAI_API_KEY"] = "test-key"
        os.environ["TRANSLATION_QE_ENABLED"] = "true"
        os.environ["TRANSLATION_QE_THRESHOLD"] = "0.7"

        google_translate_mock.return_value = {
            "english_text": "Google translation text",
            "source_language": "hi",
            "target_language": "en",
            "status": "translated",
            "provider": "google_cloud_translate",
            "model": None,
            "error": None,
        }
        openai_translate_mock.return_value = {
            "english_text": "OpenAI translation text",
            "source_language": "hi",
            "target_language": "en",
            "status": "translated",
            "provider": "openai_responses",
            "model": "gpt-5.2",
            "error": None,
        }

        def qe_side_effect(source, translated, lang, config):
            if "OpenAI" in translated:
                return {"score": 0.92, "acceptable": True, "method": "gemini_llm_judge", "details": "Excellent"}
            return {"score": 0.55, "acceptable": False, "method": "gemini_llm_judge", "details": "Mediocre"}

        qe_mock.side_effect = qe_side_effect

        result = parse_document(
            "मेरा नाम राम कुमार है। मेरा मोबाइल 15 मार्च 2026 को चोरी हो गया।"
        )

        self.assertEqual(result["language"]["translation_provider"], "openai_responses")
        self.assertEqual(result["language"]["translation_quality_score"], 0.92)
        self.assertTrue(result["language"]["translation_quality_acceptable"])
        self.assertFalse(result["language"]["translation_flagged_for_review"])
        # Both providers should have been called (ensemble)
        self.assertEqual(google_translate_mock.call_count, 1)
        self.assertEqual(openai_translate_mock.call_count, 1)

    @patch("complaint_parsing._estimate_translation_quality")
    @patch("complaint_parsing._translate_to_english_via_openai")
    @patch("complaint_parsing._translate_to_english_via_google")
    def test_ensemble_flags_best_when_all_below_threshold(
        self,
        google_translate_mock,
        openai_translate_mock,
        qe_mock,
    ) -> None:
        """When all ensemble scores are below threshold, flag best for review."""
        os.environ["TRANSLATION_ENABLED"] = "true"
        os.environ["TRANSLATION_PROVIDER"] = "auto"
        os.environ["TRANSLATION_FALLBACK_PROVIDER"] = "openai"
        os.environ["TRANSLATION_PROJECT_ID"] = "test-project"
        os.environ["OPENAI_API_KEY"] = "test-key"
        os.environ["TRANSLATION_QE_ENABLED"] = "true"
        os.environ["TRANSLATION_QE_THRESHOLD"] = "0.7"

        google_translate_mock.return_value = {
            "english_text": "Google low quality",
            "source_language": "hi",
            "target_language": "en",
            "status": "translated",
            "provider": "google_cloud_translate",
            "model": None,
            "error": None,
        }
        openai_translate_mock.return_value = {
            "english_text": "OpenAI low quality",
            "source_language": "hi",
            "target_language": "en",
            "status": "translated",
            "provider": "openai_responses",
            "model": "gpt-5.2",
            "error": None,
        }

        def qe_side_effect(source, translated, lang, config):
            if "OpenAI" in translated:
                return {"score": 0.5, "acceptable": False, "method": "gemini_llm_judge", "details": "Below threshold"}
            return {"score": 0.3, "acceptable": False, "method": "gemini_llm_judge", "details": "Poor"}

        qe_mock.side_effect = qe_side_effect

        result = parse_document(
            "मेरा नाम राम कुमार है। मेरा मोबाइल चोरी हो गया।"
        )

        self.assertEqual(result["language"]["translation_provider"], "openai_responses")
        self.assertTrue(result["language"]["translation_flagged_for_review"])

    @patch("complaint_parsing._translate_to_english_via_openai")
    @patch("complaint_parsing._translate_to_english_via_google")
    def test_qe_disabled_uses_sequential_behavior(
        self,
        google_translate_mock,
        openai_translate_mock,
    ) -> None:
        """When QE is disabled, sequential path is used — second provider never called."""
        os.environ["TRANSLATION_ENABLED"] = "true"
        os.environ["TRANSLATION_PROVIDER"] = "auto"
        os.environ["TRANSLATION_FALLBACK_PROVIDER"] = "openai"
        os.environ["TRANSLATION_PROJECT_ID"] = "test-project"
        os.environ["OPENAI_API_KEY"] = "test-key"
        os.environ["TRANSLATION_QE_ENABLED"] = "false"

        google_translate_mock.return_value = {
            "english_text": "Google translation",
            "source_language": "hi",
            "target_language": "en",
            "status": "translated",
            "provider": "google_cloud_translate",
            "model": None,
            "error": None,
        }

        result = parse_document(
            "मेरा नाम राम कुमार है। मेरा मोबाइल चोरी हो गया।"
        )

        self.assertEqual(result["language"]["translation_provider"], "google_cloud_translate")
        self.assertEqual(google_translate_mock.call_count, 1)
        self.assertEqual(openai_translate_mock.call_count, 0)

    def test_parse_document_includes_timing_metadata(self) -> None:
        """Parsed result contains timing dict with expected keys."""
        result = parse_document(CALIBRATION_COMPLAINT_1)
        timing = result["meta"]["timing"]
        self.assertIn("language_detection_ms", timing)
        self.assertIn("translation_ms", timing)
        self.assertIn("heuristic_extraction_ms", timing)
        self.assertIn("llm_extraction_ms", timing)
        self.assertIn("fir_draft_ms", timing)
        for key, value in timing.items():
            self.assertGreaterEqual(value, 0, f"timing[{key}] should be non-negative")

    def test_parse_document_calls_progress_callback(self) -> None:
        """Progress callback receives expected step IDs in order."""
        received_steps = []

        def callback(step_id, label, details):
            received_steps.append(step_id)

        parse_document(CALIBRATION_COMPLAINT_1, progress_callback=callback)
        expected_steps = [
            "detecting_language",
            "translating",
            "extracting_fields",
            "llm_extraction",
            "generating_fir",
            "complete",
        ]
        # All expected steps should appear and in order
        for step in expected_steps:
            self.assertIn(step, received_steps)
        # Verify ordering
        indices = [received_steps.index(s) for s in expected_steps]
        self.assertEqual(indices, sorted(indices))


class TestDualLanguageExtraction(unittest.TestCase):
    """Tests for dual-language LLM extraction and original-language evidence validation."""

    HINDI_ORIGINAL = (
        "श्रीमान, मैं राजेश कुमार निवासी मोहल्ला नया बाजार से प्रार्थना करता हूँ कि "
        "दिनांक 15-03-2026 को रात 10:30 बजे मेरे घर में चोरी हो गई।"
    )
    ENGLISH_TRANSLATION = (
        "Sir, I Rajesh Kumar resident of Mohalla Naya Bazaar submit that "
        "on 15-03-2026 at 10:30 PM theft occurred in my house."
    )

    @patch("complaint_parsing.get_question_guided_extraction_config")
    @patch("complaint_parsing.urllib.request.urlopen")
    def test_dual_language_prompt_includes_both_texts(
        self, urlopen_mock, config_mock
    ) -> None:
        """When original_text differs from english_text, the prompt contains both."""
        config_mock.return_value = {
            "enabled": True,
            "api_key": "test-key",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o-mini",
            "reasoning_effort": "none",
        }
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "output": [{"type": "message", "content": [{"type": "output_text", "text": "{}"}]}]
        }).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        urlopen_mock.return_value = mock_response

        _extract_complaint_insights_via_openai(
            self.ENGLISH_TRANSLATION,
            {"who": {}, "what": {}, "when": {}, "where": {}, "why": {}, "how": {}},
            original_text=self.HINDI_ORIGINAL,
        )

        sent_data = json.loads(urlopen_mock.call_args[0][0].data.decode())
        user_msg = sent_data["input"][-1]["content"][0]["text"]
        self.assertIn("Original text:", user_msg)
        self.assertIn("English translation:", user_msg)
        self.assertIn("राजेश कुमार", user_msg)
        self.assertIn("Rajesh Kumar", user_msg)
        self.assertNotIn("Complaint text:", user_msg)

    @patch("complaint_parsing.get_question_guided_extraction_config")
    @patch("complaint_parsing.urllib.request.urlopen")
    def test_single_language_prompt_unchanged_for_english(
        self, urlopen_mock, config_mock
    ) -> None:
        """When original_text is None, the prompt uses 'Complaint text:' format."""
        config_mock.return_value = {
            "enabled": True,
            "api_key": "test-key",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o-mini",
            "reasoning_effort": "none",
        }
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "output": [{"type": "message", "content": [{"type": "output_text", "text": "{}"}]}]
        }).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        urlopen_mock.return_value = mock_response

        _extract_complaint_insights_via_openai(
            self.ENGLISH_TRANSLATION,
            {"who": {}, "what": {}, "when": {}, "where": {}, "why": {}, "how": {}},
        )

        sent_data = json.loads(urlopen_mock.call_args[0][0].data.decode())
        user_msg = sent_data["input"][-1]["content"][0]["text"]
        self.assertIn("Complaint text:", user_msg)
        self.assertNotIn("Original text:", user_msg)
        self.assertNotIn("English translation:", user_msg)

    @patch("complaint_parsing._extract_complaint_insights_via_openai")
    @patch("complaint_parsing._translate_to_english_via_openai")
    @patch("complaint_parsing._translate_to_english_via_google")
    def test_evidence_from_original_language_passes_validation(
        self, google_mock, openai_translate_mock, extraction_mock
    ) -> None:
        """Evidence snippet in Hindi passes validation when combined_source_text includes original."""
        hindi_text = self.HINDI_ORIGINAL
        english_text = self.ENGLISH_TRANSLATION
        hindi_evidence = "मोहल्ला नया बाजार"

        os.environ["TRANSLATION_ENABLED"] = "true"
        os.environ["TRANSLATION_PROVIDER"] = "auto"
        os.environ["TRANSLATION_PROJECT_ID"] = "test"

        google_mock.return_value = {
            "english_text": english_text,
            "source_language": "hi",
            "target_language": "en",
            "status": "translated",
            "provider": "google_cloud_translate",
            "model": None,
            "error": None,
        }
        openai_translate_mock.return_value = {
            "english_text": "",
            "status": "unavailable",
            "provider": "openai_responses",
            "model": None,
            "error": "Not called",
            "source_language": "hi",
            "target_language": "en",
        }

        extraction_mock.return_value = {
            "complaint_summary": "Theft complaint by Rajesh Kumar",
            "review_questions": [],
            "answers": {
                "where": {
                    "answer": "Mohalla Naya Bazaar",
                    "confidence": "high",
                    "evidence": [hindi_evidence],
                },
            },
        }

        result = parse_document(hindi_text)

        where_validation = (
            result.get("meta", {})
            .get("extraction", {})
            .get("question_guided_validation", {})
            .get("rejected_reasons", {})
            .get("where")
        )
        self.assertIsNone(
            where_validation,
            "Hindi evidence should not be rejected — combined_source_text includes original",
        )


if __name__ == "__main__":
    unittest.main()

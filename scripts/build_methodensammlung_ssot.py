#!/usr/bin/env python3
"""
Build a normalized Excel workbook for Polarstern's Methodensammlung.

The environment for this task does not include openpyxl/xlsxwriter, so this
script reads the source XLSX via the OOXML zip parts and writes a new workbook
with a small custom XLSX writer. The source workbook remains untouched.
"""

from __future__ import annotations

import argparse
import datetime as dt
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile


NS_MAIN = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


RAW_HEADERS = [
    "#",
    "Name",
    "One-sentence description",
    "Description",
    "Purpose",
    "Group Form",
    "Time Estimate",
    "Materials",
    "Notes",
    "Tag 1",
    "Tag 2",
    "Tag 3",
    "Tag 4",
    "Tag 5",
]


METHOD_HEADERS = [
    "method_id",
    "legacy_row_id",
    "name_de",
    "short_description",
    "full_description",
    "primary_purpose",
    "group_form",
    "duration_min",
    "duration_max",
    "materials",
    "facilitator_notes",
    "source_notes",
    "age_min",
    "age_max",
    "group_size_min",
    "group_size_max",
    "energy_level",
    "energy_level_source",
    "intensity",
    "intensity_source",
    "movement_level",
    "movement_level_source",
    "noise_level",
    "noise_level_source",
    "indoor_outdoor",
    "indoor_outdoor_source",
    "preparation_level",
    "preparation_level_source",
    "safeguarding_flag",
    "safeguarding_flag_source",
    "status",
    "uncertainty_flag",
    "uncertainty_note",
]


METHOD_TAG_HEADERS = [
    "method_id",
    "tag_type",
    "tag_value",
    "source",
    "confidence",
]


VARIANT_HEADERS = [
    "variant_id",
    "method_id",
    "variant_name",
    "variant_label",
    "recommended_duration",
    "phase",
    "use_case",
    "energy_role",
    "social_setting",
    "instruction_short",
    "composer_card_summary",
    "active_session_prompt",
    "facilitator_tip",
    "risk_alert",
    "materials_override",
    "suitable_for_finder",
    "suitable_for_library",
    "suitable_for_composer",
    "suitable_for_active_session",
    "uncertainty_flag",
    "uncertainty_note",
]


FINDER_HEADERS = [
    "intent_id",
    "intent_label_de",
    "user_need_statement",
    "description",
    "duration_filter_min",
    "duration_filter_max",
    "energy_target",
    "class_state",
    "recommended_method_ids_or_variant_ids",
    "ranking_notes",
]


COLLECTION_HEADERS = [
    "collection_id",
    "name_de",
    "short_description",
    "editorial_rationale",
    "sort_order",
    "visibility",
    "uncertainty_flag",
    "uncertainty_note",
]


COLLECTION_ITEM_HEADERS = [
    "collection_id",
    "method_id_or_variant_id",
    "item_type",
    "sort_order",
    "reason_for_inclusion",
]


VECTOR_HEADERS = [
    "vector_id",
    "vector_name_de",
    "vector_definition",
    "notes",
]


METHOD_VECTOR_HEADERS = [
    "method_id",
    "vector_id",
    "confidence",
    "note",
]


COMPOSER_HEADERS = [
    "block_ref_id",
    "source_type",
    "source_id",
    "display_title",
    "duration_display",
    "card_summary",
    "phase",
    "energy_role",
    "icon_hint",
    "group_setting",
    "materials_hint",
    "searchable_text",
    "filter_text",
    "is_customizable",
]


UI_MAPPING_HEADERS = [
    "screen",
    "component",
    "ui_label",
    "source_sheet",
    "source_field",
    "transformation_rule",
    "fallback_rule",
    "notes",
]


MOCKUP_CONSTRAINT_HEADERS = [
    "constraint_id",
    "area",
    "rule",
    "reason",
    "severity",
]


OPEN_QUESTION_HEADERS = [
    "question_id",
    "area",
    "issue",
    "options",
    "recommended_option",
    "why",
    "blocking_or_non_blocking",
]


README_HEADERS = ["section", "key", "value"]


VECTOR_DEFINITIONS = [
    {
        "vector_id": "vector_ankommen",
        "vector_name_de": "Warm-up / Ankommen",
        "vector_definition": "Methoden fuers Ankommen, Kennenlernen und fuer erste Aktivierung am Beginn einer Einheit.",
        "notes": "Konservativ aus Roh-Tags wie Warm-Up und Kennenlernen sowie Einstieg abgeleitet.",
    },
    {
        "vector_id": "vector_aktivierung",
        "vector_name_de": "Aktivierung / Bewegung",
        "vector_definition": "Methoden mit merklicher koerperlicher Aktivierung, Auflockerung oder Bewegungsanteil.",
        "notes": "Vor allem aus Aktivierung und Bewegung, Bewegungsfoerderung und Auflockerung abgeleitet.",
    },
    {
        "vector_id": "vector_fokus",
        "vector_name_de": "Achtsamkeit / Konzentration",
        "vector_definition": "Methoden, die Aufmerksamkeit, Sinnesfokus oder konzentriertes Wahrnehmen staerken.",
        "notes": "Aus Achtsamkeit und Konzentration sowie Sinneswahrnehmung gebildet.",
    },
    {
        "vector_id": "vector_gefuehle",
        "vector_name_de": "Gefuehle / Beziehungen",
        "vector_definition": "Methoden zum Benennen, Wahrnehmen oder Teilen von Gefuehlen und Beziehungserfahrungen.",
        "notes": "Fuehrt Emotionen und soziale Bezuege zusammen, wenn die Quelle dies nahelegt.",
    },
    {
        "vector_id": "vector_staerken",
        "vector_name_de": "Staerken / Ressourcen",
        "vector_definition": "Methoden, die persoenliche Staerken, Ressourcen oder Selbstvertrauen sichtbar machen.",
        "notes": "Direkt aus Staerken erkennen, Ressourcenaktivierung und verwandten Formulierungen gebildet.",
    },
    {
        "vector_id": "vector_kooperation",
        "vector_name_de": "Kooperation / Vertrauen",
        "vector_definition": "Methoden fuer Gruppendynamik, Zusammenarbeit, Zusammenhalt und Vertrauen.",
        "notes": "Basiert auf Roh-Tags zu Gruppendynamik, Kooperation und Vertrauen.",
    },
    {
        "vector_id": "vector_reflexion",
        "vector_name_de": "Reflexion / Feedback",
        "vector_definition": "Methoden fuer Rueckblick, Rueckmeldung, Auswertung und bewussten Abschluss.",
        "notes": "Aus Reflexion und Feedback sowie ausgewaehlten Abschlusshinweisen gebildet.",
    },
    {
        "vector_id": "vector_zukunft",
        "vector_name_de": "Zukunft / Entscheidungen",
        "vector_definition": "Methoden zu Zukunftsbildern, Entscheidungsfindung und Partizipation.",
        "notes": "Direkt aus Zukunft und Entscheidungen sowie Partizipation abgeleitet.",
    },
    {
        "vector_id": "vector_kreativ",
        "vector_name_de": "Kreativitaet / Visualisierung",
        "vector_definition": "Methoden mit starkem Gestaltungs-, Bild-, Visualisierungs- oder Ideenanteil.",
        "notes": "Fuehrt Kreativitaet, Visualisierung und Phantasie nur dort zusammen, wo die Quelle dies stuetzt.",
    },
    {
        "vector_id": "vector_entspannung",
        "vector_name_de": "Entspannung / Cool-Down",
        "vector_definition": "Methoden zum Runterfahren, Regulieren und bewussten Beruhigen einer Gruppe.",
        "notes": "Aus Entspannung, Beruhigung und Cool-Down sowie ruhigen Koerperreisen gebildet.",
    },
]


VECTOR_RULES = [
    {
        "vector_id": "vector_ankommen",
        "confidence": 0.95,
        "keywords": [
            "warm-up und kennenlernen",
            "warm-up",
            "kennenlernen",
            "einstieg",
            "ankommen",
        ],
    },
    {
        "vector_id": "vector_aktivierung",
        "confidence": 0.9,
        "keywords": [
            "aktivierung und bewegung",
            "bewegungsfoerdernd",
            "bewegungsfördernd",
            "aktivierung",
            "auflockerung",
            "spazieren durch den raum",
            "im raum herum",
            "outdoor",
        ],
    },
    {
        "vector_id": "vector_fokus",
        "confidence": 0.95,
        "keywords": [
            "achtsamkeit und konzentration",
            "achtsamkeit",
            "konzentration",
            "sinneswahrnehmung",
            "stabilisierung",
            "5-finger-methode",
            "5-4-3-2-1",
        ],
    },
    {
        "vector_id": "vector_gefuehle",
        "confidence": 0.9,
        "keywords": [
            "gefuehle erkennen und einordnen",
            "gefühle erkennen und einordnen",
            "gefuehl",
            "gefühl",
            "befindlichkeitsrunde",
            "anspannung",
            "freund*innenschaft",
            "kompliment",
        ],
    },
    {
        "vector_id": "vector_staerken",
        "confidence": 0.95,
        "keywords": [
            "staerken erkennen",
            "stärken erkennen",
            "ressourcenaktivierung",
            "selbstvertrauen",
            "ressource",
            "kraft",
            "superhero",
            "stärke",
            "stärken",
        ],
    },
    {
        "vector_id": "vector_kooperation",
        "confidence": 0.95,
        "keywords": [
            "gruppendynamik und kooperation",
            "teamspiel",
            "kooperationsspiel",
            "vertrauen",
            "zusammenhalt",
            "gruppendynamik",
            "teambuilding",
        ],
    },
    {
        "vector_id": "vector_reflexion",
        "confidence": 0.95,
        "keywords": [
            "reflexion und feedback",
            "feedback geben",
            "feedback",
            "abschluss",
            "schlusspunkt",
            "rueckblick",
            "rückblick",
        ],
    },
    {
        "vector_id": "vector_zukunft",
        "confidence": 0.95,
        "keywords": [
            "zukunft und entscheidungen",
            "partizipation",
            "zukunft",
            "entscheidung",
            "vision",
            "ideenwerkstatt",
            "zukunftswerkstatt",
        ],
    },
    {
        "vector_id": "vector_kreativ",
        "confidence": 0.85,
        "keywords": [
            "kreativitaet",
            "kreativität",
            "visualisierung",
            "phantasie anregen",
            "phantasieanregend",
            "bild",
            "zeichnen",
            "plakat",
        ],
    },
    {
        "vector_id": "vector_entspannung",
        "confidence": 0.95,
        "keywords": [
            "entspannung, beruhigung und cool-down",
            "entspannungsreise",
            "cool down",
            "cool-down",
            "koerperreise",
            "körperreise",
            "body-scan",
            "ruhe",
            "beruhigen",
        ],
    },
]


COLLECTIONS = [
    {
        "collection_id": "col_ankommen",
        "name_de": "Ankommen & Kennenlernen",
        "short_description": "Leichte Einstiege fuer den Beginn einer Stunde oder eines Workshops.",
        "editorial_rationale": "Aus wiederkehrenden Warm-Up- und Kennenlern-Tags gebildet.",
        "sort_order": 1,
        "visibility": "visible",
        "uncertainty_flag": "",
        "uncertainty_note": "",
        "vectors": ["vector_ankommen"],
    },
    {
        "collection_id": "col_fokus",
        "name_de": "Fokus, Achtsamkeit & Beruhigung",
        "short_description": "Methoden zum Sammeln, Wahrnehmen und Runterfahren.",
        "editorial_rationale": "Baut auf den Roh-Tags zu Achtsamkeit, Konzentration und Cool-Down auf.",
        "sort_order": 2,
        "visibility": "visible",
        "uncertainty_flag": "",
        "uncertainty_note": "",
        "vectors": ["vector_fokus", "vector_entspannung"],
    },
    {
        "collection_id": "col_gefuehle",
        "name_de": "Gefuehle & Beziehungen",
        "short_description": "Methoden zum Benennen, Austauschen und Einordnen sozialer und emotionaler Zustaende.",
        "editorial_rationale": "Konservativ aus Gefuehle-, Vertrauen- und Beziehungsbezuegen zusammengefuehrt.",
        "sort_order": 3,
        "visibility": "visible",
        "uncertainty_flag": "",
        "uncertainty_note": "",
        "vectors": ["vector_gefuehle"],
    },
    {
        "collection_id": "col_staerken",
        "name_de": "Staerken & Ressourcen",
        "short_description": "Methoden, die positive Eigenschaften, Ressourcen und Selbstvertrauen sichtbar machen.",
        "editorial_rationale": "Direkt aus Staerken erkennen und Ressourcenaktivierung abgeleitet.",
        "sort_order": 4,
        "visibility": "visible",
        "uncertainty_flag": "",
        "uncertainty_note": "",
        "vectors": ["vector_staerken"],
    },
    {
        "collection_id": "col_kooperation",
        "name_de": "Kooperation & Vertrauen",
        "short_description": "Gruppenorientierte Methoden fuer Zusammenarbeit, Abstimmung und gegenseitige Unterstuetzung.",
        "editorial_rationale": "Gruppendynamik, Kooperation und Vertrauen sind im Rohmaterial eng gekoppelt.",
        "sort_order": 5,
        "visibility": "visible",
        "uncertainty_flag": "",
        "uncertainty_note": "",
        "vectors": ["vector_kooperation"],
    },
    {
        "collection_id": "col_zukunft",
        "name_de": "Zukunft & Entscheidungen",
        "short_description": "Methoden fuer Zukunftsbilder, Einigungsprozesse und partizipative Planung.",
        "editorial_rationale": "Basiert auf dem klar abgegrenzten Roh-Cluster Zukunft und Entscheidungen.",
        "sort_order": 6,
        "visibility": "visible",
        "uncertainty_flag": "",
        "uncertainty_note": "",
        "vectors": ["vector_zukunft"],
    },
    {
        "collection_id": "col_reflexion",
        "name_de": "Reflexion & Abschluss",
        "short_description": "Methoden fuer Rueckmeldung, Auswertung und bewusste Schlussmomente.",
        "editorial_rationale": "Kombiniert Reflexion und Feedback mit expliziten Abschlussverwendungen aus der Quelle.",
        "sort_order": 7,
        "visibility": "visible",
        "uncertainty_flag": "",
        "uncertainty_note": "",
        "vectors": ["vector_reflexion"],
    },
]


FINDER_INTENTS = [
    {
        "intent_id": "intent_ankommen",
        "intent_label_de": "Ankommen & Kennenlernen",
        "user_need_statement": "Ich brauche einen leichten Einstieg, damit die Gruppe ankommt und sich begegnet.",
        "description": "Situation-first Einstieg fuer erste Minuten, neue Gruppen oder lockere Starts.",
        "duration_filter_min": "",
        "duration_filter_max": "",
        "energy_target": "mittel",
        "class_state": "noch nicht verbunden",
        "recommended_method_ids_or_variant_ids": "m001,m003,m015,m016,m042,m083",
        "ranking_notes": "Priorisiert Methoden mit starken Warm-Up- oder Kennenlern-Signalen.",
    },
    {
        "intent_id": "intent_kurz_aktivieren",
        "intent_label_de": "Kurz aktivieren",
        "user_need_statement": "Ich habe nur wenige Minuten und will Bewegung oder Wachheit in die Gruppe bringen.",
        "description": "Geeignet fuer kurze Energizer oder Unterbrechungen nach laengerem Sitzen.",
        "duration_filter_min": 0,
        "duration_filter_max": 10,
        "energy_target": "hoch",
        "class_state": "muede oder trage",
        "recommended_method_ids_or_variant_ids": "m006,m017,m018,m042,m080",
        "ranking_notes": "Wo keine exakte Dauer vorliegt, werden nur klar kurze Methoden nach vorne gezogen.",
    },
    {
        "intent_id": "intent_fokus",
        "intent_label_de": "Fokus zurueckholen",
        "user_need_statement": "Die Gruppe ist abgelenkt; ich brauche Konzentration ohne lange Erklaerung.",
        "description": "Baut auf Achtsamkeits-, Konzentrations- und Wahrnehmungs-Tags auf.",
        "duration_filter_min": "",
        "duration_filter_max": "",
        "energy_target": "mittel",
        "class_state": "unruhig oder verstreut",
        "recommended_method_ids_or_variant_ids": "m027,m028,m030,m031,m046",
        "ranking_notes": "Bevorzugt klare, niedrigschwellige Konzentrationsspiele mit wenig Material.",
    },
    {
        "intent_id": "intent_beruhigen",
        "intent_label_de": "Beruhigen & runterfahren",
        "user_need_statement": "Die Gruppe ist laut oder aufgedreht und braucht einen ruhigeren Uebergang.",
        "description": "Nutzt explizite Cool-Down-, Entspannungs- und Achtsamkeitssignale.",
        "duration_filter_min": "",
        "duration_filter_max": "",
        "energy_target": "niedrig",
        "class_state": "laut oder ueberreizt",
        "recommended_method_ids_or_variant_ids": "m023,m024,m026,m063,m085",
        "ranking_notes": "Methoden mit ruhigem Fokus und klarer sprachlicher Anleitung werden bevorzugt.",
    },
    {
        "intent_id": "intent_gefuehle",
        "intent_label_de": "Gefuehle ausdruecken",
        "user_need_statement": "Ich will Stimmungen sichtbar machen oder ueber Gefuehle ins Gespraech kommen.",
        "description": "Basiert auf Gefuehle erkennen und einordnen sowie verwandten Beschreibungen.",
        "duration_filter_min": "",
        "duration_filter_max": "",
        "energy_target": "niedrig",
        "class_state": "emotional oder unklar",
        "recommended_method_ids_or_variant_ids": "m002,m047,m048,m049,m058,m059",
        "ranking_notes": "Startet mit niedrigschwelligen Befindlichkeitsformaten vor offeneren Runden.",
    },
    {
        "intent_id": "intent_staerken",
        "intent_label_de": "Staerken sichtbar machen",
        "user_need_statement": "Ich moechte Ressourcen, positive Eigenschaften oder Selbstvertrauen aktivieren.",
        "description": "Grounded in Staerken erkennen, Ressourcenaktivierung und Selbstwahrnehmung.",
        "duration_filter_min": "",
        "duration_filter_max": "",
        "energy_target": "mittel",
        "class_state": "arbeitsfaehig",
        "recommended_method_ids_or_variant_ids": "m019,m040,m041,m053,m065,m078",
        "ranking_notes": "Mischt wahrnehmungsorientierte und gestalterische Staerkenmethoden.",
    },
    {
        "intent_id": "intent_kooperation",
        "intent_label_de": "Kooperation foerdern",
        "user_need_statement": "Ich brauche eine Methode, bei der die Gruppe gemeinsam handeln und sich abstimmen muss.",
        "description": "Leitet sich aus Teamspiel-, Kooperations- und Gruppendynamiksignalen ab.",
        "duration_filter_min": "",
        "duration_filter_max": "",
        "energy_target": "hoch",
        "class_state": "gemeinsame Aufgabe gesucht",
        "recommended_method_ids_or_variant_ids": "m007,m008,m011,m056,m073,m074",
        "ranking_notes": "Bevorzugt deutliche gemeinsame Aufgaben statt reiner Diskussionsformate.",
    },
    {
        "intent_id": "intent_vertrauen",
        "intent_label_de": "Vertrauen aufbauen",
        "user_need_statement": "Ich moechte Beziehung, Aufmerksamkeit oder gegenseitige Unterstuetzung staerken.",
        "description": "Nutzt die Rohsignale Vertrauen, Gruppendynamik und ausgewaehlte Beziehungsmethoden.",
        "duration_filter_min": "",
        "duration_filter_max": "",
        "energy_target": "mittel",
        "class_state": "vorsichtig oder noch nicht sicher",
        "recommended_method_ids_or_variant_ids": "m025,m061_v_kreis,m061_v_paare,m067,m069_v_abschluss",
        "ranking_notes": "Ordnet koerperlich sensiblere Formate spaeter ein und verweist auf Risiko-Hinweise.",
    },
    {
        "intent_id": "intent_reflexion",
        "intent_label_de": "Reflexion & Abschluss",
        "user_need_statement": "Ich brauche einen klaren Rueckblick oder einen bewussten Schlusspunkt.",
        "description": "Fasst Feedback-, Abschluss- und Reflexionsformate zusammen.",
        "duration_filter_min": "",
        "duration_filter_max": "",
        "energy_target": "niedrig",
        "class_state": "am Ende einer Einheit",
        "recommended_method_ids_or_variant_ids": "m020_v_twitter,m020_v_hochgleichief,m020_v_daumen,m021,m044,m069_v_abschluss",
        "ranking_notes": "Kurze Feedback-Formate zuerst; offenere Austauschformen danach.",
    },
    {
        "intent_id": "intent_zukunft",
        "intent_label_de": "Zukunft & Entscheidungen",
        "user_need_statement": "Ich will Zukunftsbilder, Auswahlprozesse oder partizipative Ideenentwicklung anstossen.",
        "description": "Grounded in Zukunft und Entscheidungen sowie Partizipation.",
        "duration_filter_min": "",
        "duration_filter_max": "",
        "energy_target": "mittel",
        "class_state": "planend oder suchend",
        "recommended_method_ids_or_variant_ids": "m035,m036,m037,m038,m039,m070",
        "ranking_notes": "Sortiert von Problemaufsammlung zu Auswahl und Zukunftsbild.",
    },
]


VARIANT_DEFINITIONS = [
    {
        "variant_id": "m005_v_platzwechsel",
        "method_id": "m005",
        "variant_name": "Platzwechsel-Variante",
        "variant_label": "Mit Platztausch",
        "recommended_duration": "",
        "phase": "Ankommen",
        "use_case": "Kennenlernen",
        "energy_role": "aktivieren",
        "social_setting": "Sitzkreis mit Platzwechsel",
        "instruction_short": "Fragen stellen und bei passender Antwort die Plaetze tauschen.",
        "composer_card_summary": "Kennenlernformat mit mehr Bewegung als die reine Sitzkreisversion.",
        "active_session_prompt": "Stelle klare Wer-von-euch-Fragen und halte das Platztauschen kurz und zuegig.",
        "facilitator_tip": "Einzelne Antworten ruhig nachfragen, wenn daraus Kontakt entsteht.",
        "risk_alert": "",
        "materials_override": "",
        "suitable_for_finder": "ja",
        "suitable_for_library": "ja",
        "suitable_for_composer": "ja",
        "suitable_for_active_session": "ja",
        "uncertainty_flag": "",
        "uncertainty_note": "Explizite Alternative in der Beschreibung.",
    },
    {
        "variant_id": "m016_v_3ecken",
        "method_id": "m016",
        "variant_name": "3-Ecken-Variante",
        "variant_label": "Mit 3 Ecken",
        "recommended_duration": "",
        "phase": "Ankommen",
        "use_case": "Positionierung",
        "energy_role": "aktivieren",
        "social_setting": "Gruppe im Raum",
        "instruction_short": "Drei Antwortoptionen im Raum markieren und die Gruppe positionieren.",
        "composer_card_summary": "Reduziert die Antwortkomplexitaet fuer juengere oder unentschlossene Gruppen.",
        "active_session_prompt": "Frage stellen, drei klare Positionen benennen und Bewegung im Raum zulassen.",
        "facilitator_tip": "Eine offene Ecke nur nutzen, wenn genug Zeit fuer kurze Begruendungen bleibt.",
        "risk_alert": "",
        "materials_override": "",
        "suitable_for_finder": "ja",
        "suitable_for_library": "ja",
        "suitable_for_composer": "ja",
        "suitable_for_active_session": "ja",
        "uncertainty_flag": "",
        "uncertainty_note": "Variante direkt im Methodentitel angelegt.",
    },
    {
        "variant_id": "m020_v_twitter",
        "method_id": "m020",
        "variant_name": "Twitter-Feedback",
        "variant_label": "Hashtag-Feedback",
        "recommended_duration": "",
        "phase": "Reflektieren",
        "use_case": "Feedback",
        "energy_role": "abschliessen",
        "social_setting": "Einzeln im Plenum",
        "instruction_short": "Feedback als kurzen Hashtag notieren oder nennen.",
        "composer_card_summary": "Sehr kompaktes Abschlussformat fuer schnelle Rueckmeldungen.",
        "active_session_prompt": "Bitte um einen klaren Hashtag pro Person und sammele die Begriffe sichtbar.",
        "facilitator_tip": "Kurze Rueckfragen nur dort stellen, wo ein Hashtag erklaerungsbeduerftig ist.",
        "risk_alert": "",
        "materials_override": "",
        "suitable_for_finder": "ja",
        "suitable_for_library": "ja",
        "suitable_for_composer": "ja",
        "suitable_for_active_session": "ja",
        "uncertainty_flag": "",
        "uncertainty_note": "Explizite Unterform in der Quelle.",
    },
    {
        "variant_id": "m020_v_hochgleichief",
        "method_id": "m020",
        "variant_name": "Hoch-Gleich-Tief",
        "variant_label": "Koerperliches Stimmungsbarometer",
        "recommended_duration": "",
        "phase": "Reflektieren",
        "use_case": "Feedback",
        "energy_role": "abschliessen",
        "social_setting": "Gruppe im Raum",
        "instruction_short": "Aufstehen, sitzen bleiben oder auf den Stuhl steigen je nach Rueckmeldung.",
        "composer_card_summary": "Schnelles Feedbackformat mit sichtbarer Gruppenstimmung.",
        "active_session_prompt": "Formuliere die Bewertungsstufen klar und gib der Gruppe kurz Zeit zur Positionierung.",
        "facilitator_tip": "Die Rueckmeldung bleibt knapp; einzelne Stimmen nur freiwillig vertiefen.",
        "risk_alert": "Auf sichere Stuhl-Nutzung achten, wenn die hoechste Stufe auf dem Stuhl steht.",
        "materials_override": "",
        "suitable_for_finder": "ja",
        "suitable_for_library": "ja",
        "suitable_for_composer": "ja",
        "suitable_for_active_session": "ja",
        "uncertainty_flag": "",
        "uncertainty_note": "Explizite Unterform in der Quelle.",
    },
    {
        "variant_id": "m020_v_daumen",
        "method_id": "m020",
        "variant_name": "Daumen-Feedback",
        "variant_label": "Daumen hoch / gleich / runter",
        "recommended_duration": "",
        "phase": "Reflektieren",
        "use_case": "Feedback",
        "energy_role": "abschliessen",
        "social_setting": "Plenum",
        "instruction_short": "Rueckmeldung nonverbal per Daumenzeichen geben.",
        "composer_card_summary": "Niedrigschwelliger Abschluss ohne Material.",
        "active_session_prompt": "Stelle eine klare Abschlussfrage und lasse die Gruppe gleichzeitig abstimmen.",
        "facilitator_tip": "Gut geeignet, wenn wenig Zeit bleibt oder Offenheit in der Gruppe noch gering ist.",
        "risk_alert": "",
        "materials_override": "",
        "suitable_for_finder": "ja",
        "suitable_for_library": "ja",
        "suitable_for_composer": "ja",
        "suitable_for_active_session": "ja",
        "uncertainty_flag": "",
        "uncertainty_note": "Explizite Unterform in der Quelle.",
    },
    {
        "variant_id": "m061_v_kreis",
        "method_id": "m061",
        "variant_name": "Kreis-Vertrauensuebung",
        "variant_label": "Im 5-8er-Kreis",
        "recommended_duration": "",
        "phase": "Vertiefen",
        "use_case": "Vertrauen aufbauen",
        "energy_role": "vertiefen",
        "social_setting": "5-8 Personen im Kreis",
        "instruction_short": "Eine Person laesst sich mit geschlossenen Augen in die Gruppe fallen.",
        "composer_card_summary": "Koerperlich deutliche Vertrauensuebung fuer kleine Kreise.",
        "active_session_prompt": "Kreis eng halten, Sicherheitsabstand klein halten und die Person in der Mitte gut einweisen.",
        "facilitator_tip": "Nur nutzen, wenn die Gruppe schon etwas Sicherheit miteinander hat.",
        "risk_alert": "Koerperkontakt und geschlossene Augen erfordern klare Rahmung und enge Aufsicht.",
        "materials_override": "Ausreichend Platz",
        "suitable_for_finder": "ja",
        "suitable_for_library": "ja",
        "suitable_for_composer": "ja",
        "suitable_for_active_session": "ja",
        "uncertainty_flag": "",
        "uncertainty_note": "Variante explizit in der Quelle.",
    },
    {
        "variant_id": "m061_v_paare",
        "method_id": "m061",
        "variant_name": "Partner-Fallvariante",
        "variant_label": "Zu zweit rueckwaerts fallen",
        "recommended_duration": "",
        "phase": "Vertiefen",
        "use_case": "Vertrauen aufbauen",
        "energy_role": "vertiefen",
        "social_setting": "Paare",
        "instruction_short": "Abwechselnd rueckwaerts in die Arme der Partnerperson fallen lassen.",
        "composer_card_summary": "Kompaktere Vertrauensvariante als der grosse Kreis.",
        "active_session_prompt": "Paare stabil aufstellen und vor dem Fallen klaeren, wie gefangen wird.",
        "facilitator_tip": "Vorher pruefen, ob beide Personen die Uebung wirklich mittragen moechten.",
        "risk_alert": "Nur mit klarer Sicherheitsanleitung und aufmerksamer Aufsicht einsetzen.",
        "materials_override": "Ausreichend Platz",
        "suitable_for_finder": "ja",
        "suitable_for_library": "ja",
        "suitable_for_composer": "ja",
        "suitable_for_active_session": "ja",
        "uncertainty_flag": "",
        "uncertainty_note": "Variante explizit in der Quelle.",
    },
    {
        "variant_id": "m069_v_warmup",
        "method_id": "m069",
        "variant_name": "Warm-up-Einsatz",
        "variant_label": "Als Einstieg",
        "recommended_duration": "",
        "phase": "Ankommen",
        "use_case": "Staerken sichtbar machen",
        "energy_role": "aktivieren",
        "social_setting": "Sesselkreis",
        "instruction_short": "Den Tauschmarkt frueh einsetzen, um vorhandene Staerken in die Gruppe zu holen.",
        "composer_card_summary": "Offener Staerken-Tausch als lebendiger Einstieg mit hoher Beteiligung.",
        "active_session_prompt": "Eroeffne den Basar mit einem eigenen Beispiel und ziehe stille Personen bewusst mit hinein.",
        "facilitator_tip": "Darauf achten, dass nur Ressourcen und keine Defizite gehandelt werden.",
        "risk_alert": "Freiwilligkeit sichern und niemanden in Selbstdarstellung draengen.",
        "materials_override": "",
        "suitable_for_finder": "ja",
        "suitable_for_library": "ja",
        "suitable_for_composer": "ja",
        "suitable_for_active_session": "ja",
        "uncertainty_flag": "ja",
        "uncertainty_note": "Quelle nennt die Methode als Warming-up und Schlusspunkt; Dauer nur als 30 Min. oder mehr.",
    },
    {
        "variant_id": "m069_v_abschluss",
        "method_id": "m069",
        "variant_name": "Abschluss-Einsatz",
        "variant_label": "Als Schlusspunkt",
        "recommended_duration": "",
        "phase": "Abschluss",
        "use_case": "Reflexion",
        "energy_role": "abschliessen",
        "social_setting": "Sesselkreis",
        "instruction_short": "Den Tauschmarkt spaeter einsetzen, um gesehene Staerken und Qualitaeten zu spiegeln.",
        "composer_card_summary": "Staerkenbasar als reflexiver Gruppenabschluss.",
        "active_session_prompt": "Spiegele beobachtete Staerken, halte den Tausch wertschatzend und achte auf Beteiligung aller.",
        "facilitator_tip": "Vergessene Personen aktiv einladen, ohne Druck zu machen.",
        "risk_alert": "Rueckmeldungen sollten ressourcenorientiert bleiben; keine Defizite verhandeln.",
        "materials_override": "",
        "suitable_for_finder": "ja",
        "suitable_for_library": "ja",
        "suitable_for_composer": "ja",
        "suitable_for_active_session": "ja",
        "uncertainty_flag": "ja",
        "uncertainty_note": "Quelle nennt die Methode als Warming-up und Schlusspunkt; Dauer nur als 30 Min. oder mehr.",
    },
]


METHOD_OVERRIDES = {
    "11": {
        "duration_min": 10,
        "duration_max": 15,
        "source_notes": ["Arbeitszeit 10-15 Minuten explizit in der Beschreibung; Vorstellungsphase nicht separat ausgewiesen."],
        "uncertainty_flag": "ja",
        "uncertainty_note": "Dauer aus der Beschreibung abgeleitet; Gesamtzeit kann durch Praesentation laenger sein.",
    },
    "12": {
        "duration_min": 18,
        "duration_max": 18,
        "source_notes": ["18 Minuten explizit in der Beschreibung."],
    },
    "61": {
        "group_size_min": 5,
        "group_size_max": 8,
        "source_notes": ["Kreisgroesse 5-8 Personen explizit in der Beschreibung."],
    },
    "69": {
        "duration_min": 30,
        "duration_max": "",
        "source_notes": ["Quelle nennt 30 Min. oder mehr; nur die Untergrenze 30 wurde uebernommen."],
        "uncertainty_flag": "ja",
        "uncertainty_note": "Dauer in der Quelle offen nach oben.",
    },
    "80": {
        "duration_min": "",
        "duration_max": 5,
        "source_notes": ["Notiz nennt dauert maximal 5 Minuten; nur die Obergrenze wurde uebernommen."],
        "uncertainty_flag": "ja",
        "uncertainty_note": "Quelle beschreibt eine Maximaldauer, keine exakte Standarddauer.",
    },
    "19": {
        "uncertainty_flag": "ja",
        "uncertainty_note": "Doppelter Methodentitel im Import; als eigener Datensatz belassen, weil sich Details unterscheiden.",
    },
    "45": {
        "uncertainty_flag": "ja",
        "uncertainty_note": "Doppelter Methodentitel im Import; als eigener Datensatz belassen, weil sich Details unterscheiden.",
    },
    "62": {
        "status": "unvollstaendig",
        "uncertainty_flag": "ja",
        "uncertainty_note": "Beschreibung, Zweck und Material fehlen im Import.",
    },
    "70": {
        "uncertainty_flag": "ja",
        "uncertainty_note": "Purpose-Spalte im Import leer; Zuordnung nur ueber Tags und Beschreibung.",
    },
    "73": {
        "uncertainty_flag": "ja",
        "uncertainty_note": "Zeitspanne in der Beschreibung nur als variables Beispiel 15/20/30 Min. genannt.",
    },
    "57": {
        "uncertainty_flag": "ja",
        "uncertainty_note": "Purpose-Spalte im Import leer; Inhalt und Tags sind vorhanden.",
    },
}


TOPIC_RULES = [
    ("Staerken", ["stärke", "stärken", "staerken", "ressourcenaktivierung", "ressource", "selbstvertrauen", "kraft"]),
    ("Zukunftsperspektiven", ["zukunft", "entscheidung", "ideenwerkstatt", "zukunftswerkstatt", "vision"]),
    ("Achtsamkeit", ["achtsamkeit", "sinneswahrnehmung", "stabilisierung", "body-scan", "koerperreise", "körperreise", "entspannung"]),
    ("Resilienz", ["resilienz", "klassenresilienz"]),
    ("Emotionen", ["gefühl", "gefuehl", "befindlich", "anspannung", "stimmung"]),
    ("Beziehungen", ["vertrauen", "kompliment", "feedback", "freund", "zuhören", "zuhoeren"]),
    ("Gruppendynamik", ["gruppendynamik", "kooperation", "teamspiel", "klassengemeinschaft", "zusammenhalt"]),
]


SKILL_RULES = [
    ("Kennenlernen", ["kennenlernen", "warm-up", "ankommen"]),
    ("Kooperation", ["kooperation", "kooperationsspiel", "teamspiel", "gruppendynamik", "zusammenhalt"]),
    ("Konzentration", ["konzentration", "achtsamkeit", "sinneswahrnehmung"]),
    ("Selbstwahrnehmung", ["selbstwahrnehmung", "befindlich", "gefuehl", "gefühl"]),
    ("Vertrauen", ["vertrauen"]),
    ("Reflexion", ["reflexion", "feedback", "abschluss"]),
    ("Kreativitaet", ["kreativ", "phantasie", "visualisierung", "zeichnen", "plakat"]),
    ("Partizipation", ["partizipation", "ideen", "entscheidung"]),
    ("Bewegung", ["bewegung", "aktivierung", "auflockerung", "bewegungsfoerdernd", "bewegungsfördernd"]),
]


PHASE_RULES = [
    ("Ankommen", ["warm-up und kennenlernen", "warm-up", "kennenlernen", "einstieg"]),
    ("Aktivieren", ["aktivierung und bewegung", "aktivierung", "auflockerung", "bewegungsfoerdernd", "bewegungsfördernd"]),
    ("Fokussieren", ["achtsamkeit und konzentration", "konzentration", "sinneswahrnehmung"]),
    ("Beruhigen", ["entspannung, beruhigung und cool-down", "entspannungsreise", "cool down", "cool-down", "ruhe"]),
    ("Reflektieren", ["reflexion und feedback", "feedback"]),
    ("Abschluss", ["schlusspunkt", "abschluss"]),
    ("Ueberleitung", ["ueberleitungen", "überleitungen"]),
    ("Vertiefen", ["stärken erkennen", "staerken erkennen", "ressourcenaktivierung", "zukunft und entscheidungen", "partizipation", "erklärungen und inhalte", "erklärungen", "visualisierung"]),
]


USE_CASE_RULES = [
    ("Kennenlernen", ["kennenlernen", "warm-up"]),
    ("Energizer", ["aktivierung", "auflockerung", "bewegung"]),
    ("Fokus zurueckholen", ["konzentration", "achtsamkeit", "sinneswahrnehmung"]),
    ("Gefuehle ausdruecken", ["gefühl", "gefuehl", "befindlich", "anspannung"]),
    ("Staerken sichtbar machen", ["stärke", "stärken", "staerken", "ressource", "selbstvertrauen"]),
    ("Kooperation foerdern", ["kooperation", "kooperationsspiel", "teamspiel", "gruppendynamik"]),
    ("Vertrauen aufbauen", ["vertrauen"]),
    ("Abschluss / Reflexion", ["feedback", "reflexion", "abschluss", "schlusspunkt"]),
    ("Zukunft erkunden", ["zukunft", "entscheidung", "vision"]),
    ("Partizipation ermoeglichen", ["partizipation", "ideenwerkstatt"]),
]


MOCKUP_CONSTRAINTS = [
    {
        "constraint_id": "mc_001",
        "area": "Content titles",
        "rule": "Reale Methodentitel aus dem Import ueberschreiben Mockup-Platzhalter immer.",
        "reason": "Die Methodenliste ist die fachliche Quelle; Mockups liefern nur UI-Logik.",
        "severity": "high",
    },
    {
        "constraint_id": "mc_002",
        "area": "Taxonomy",
        "rule": "Reale Themen, Tags und konservative NEW_CONTROLLED_TAXONOMY schlagen jede fiktive Mockup-Taxonomie.",
        "reason": "Produktlogik darf die Fachlogik strukturieren, aber nicht ersetzen.",
        "severity": "high",
    },
    {
        "constraint_id": "mc_003",
        "area": "Duration",
        "rule": "Dauerchips duerfen nur reale oder konservativ aus der Quelle normalisierte Werte zeigen.",
        "reason": "Zeitangaben beeinflussen Auswahl, Planung und Moderation direkt.",
        "severity": "high",
    },
    {
        "constraint_id": "mc_004",
        "area": "Risk and facilitation",
        "rule": "Facilitator- und Risiko-Hinweise muessen paedagogisch plausibel bleiben und duerfen nicht aus Mockups erfunden werden.",
        "reason": "Die App darf reale Workshop-Praxis nicht falsch absichern.",
        "severity": "high",
    },
    {
        "constraint_id": "mc_005",
        "area": "Product logic",
        "rule": "Mockups duerfen Layout, Interaktion und Navigationsmuster liefern, aber keine fiktionale Inhaltsstruktur in die SSOT einschreiben.",
        "reason": "Die SSOT soll produktbereit und fachlich belastbar bleiben.",
        "severity": "high",
    },
    {
        "constraint_id": "mc_006",
        "area": "Finder",
        "rule": "Situation-first Finder-Intents muessen auf wiederkehrenden Quellmustern beruhen und bei Unsicherheit offen als kontrollierte Produkt-Abstraktion markiert werden.",
        "reason": "Die Quelle enthaelt Tags, aber keine ausformulierte Finder-IA.",
        "severity": "medium",
    },
    {
        "constraint_id": "mc_007",
        "area": "Variants",
        "rule": "Method_Variants nur dann ausspielen, wenn im Import eine klare Unterform, Dauer- oder Einsatzvariante beschrieben ist.",
        "reason": "Sonst wuerde die UI mehr Fachlogik behaupten als vorhanden ist.",
        "severity": "high",
    },
    {
        "constraint_id": "mc_008",
        "area": "Frontend design system",
        "rule": "Frontend muss Aurora-Palette, Intentional Asymmetry, No-Line Rule, Chau Philomene One nur fuer editoriale Display-Momente, Roboto fuer funktionale UI, Gradient-CTA und Surface-Layering/Glass respektieren.",
        "reason": "Diese Designvorgaben wurden durch DESIGN.md und die verfuegbaren HTML-Exporte konkret bestaetigt.",
        "severity": "high",
    },
    {
        "constraint_id": "mc_009",
        "area": "Duration UI",
        "rule": "Duration chips, Karten-Metadaten und Timeline-Labels muessen verborgen bleiben, wenn keine grounded duration vorhanden ist.",
        "reason": "Die Quelle enthaelt viele Methoden ohne belastbare Dauer; leere Werte sind ehrlicher als Scheingenauigkeit.",
        "severity": "high",
    },
]


OPEN_QUESTIONS = [
    {
        "question_id": "oq_001",
        "area": "Mockup baseline",
        "issue": "DESIGN.md sowie die fuenf HTML-Exporte waren verfuegbar und wurden fuer Produktlogik-Alignment genutzt. Offen ist nur, ob diese Dateien den finalen Referenzstand oder einen explorativen Zwischenstand repraesentieren.",
        "options": "A) Diese Dateien als aktuelle UI-Baseline behandeln; B) bei neueren Exporten gezielt gegenpruefen.",
        "recommended_option": "A",
        "why": "Die aktuelle SSOT ist jetzt mit den verfuegbaren Design- und Mockup-Dateien abgestimmt und bleibt dabei fachlich quellentreu.",
        "blocking_or_non_blocking": "non-blocking",
    },
    {
        "question_id": "oq_002",
        "area": "Legacy numbering",
        "issue": "Im Import fehlen die Legacy-Nummern 75-77.",
        "options": "A) Als historische Luecke dokumentieren; B) fehlende Zeilen spaeter aus Originalquellen ergaenzen.",
        "recommended_option": "A",
        "why": "Die vorhandenen 82 Zeilen koennen sauber verarbeitet werden, ohne Nummern kuenstlich aufzufuellen.",
        "blocking_or_non_blocking": "non-blocking",
    },
    {
        "question_id": "oq_003",
        "area": "Duplicate methods",
        "issue": "Der Titel Staerken-Tiere kommt in Legacy-Zeile 19 und 45 doppelt vor, mit leicht unterschiedlichen Details.",
        "options": "A) Vorlaeufig getrennt lassen; B) nach fachlicher Ruecksprache zu einer kanonischen Methode mergen.",
        "recommended_option": "A",
        "why": "Ohne sichere Merging-Regel waere ein Zusammenziehen spekulativ.",
        "blocking_or_non_blocking": "non-blocking",
    },
    {
        "question_id": "oq_004",
        "area": "Duration completeness",
        "issue": "Die Time-Estimate-Spalte ist fast durchgehend leer; einige Zeiten stehen nur in Beschreibung oder Notizen.",
        "options": "A) Nur explizite Werte aus dem Fliesstext uebernehmen; B) Dauern fachlich nachpflegen.",
        "recommended_option": "B",
        "why": "Fuer Finder- und Composer-Qualitaet waere eine gezielte Dauerpflege sehr wertvoll.",
        "blocking_or_non_blocking": "non-blocking",
    },
    {
        "question_id": "oq_005",
        "area": "Audience metadata",
        "issue": "Altersspannen fehlen im Import vollstaendig; Gruppengroessen nur punktuell.",
        "options": "A) Felder leer lassen; B) Alters- und Gruppengroessenpflege in separater Review-Runde ergaenzen.",
        "recommended_option": "A",
        "why": "Leere Werte sind ehrlicher als ungesicherte Vermutungen.",
        "blocking_or_non_blocking": "non-blocking",
    },
    {
        "question_id": "oq_006",
        "area": "Incomplete source row",
        "issue": "Legacy-Zeile 62 Selbstvertrauen Koerperuebungen enthaelt kaum fachliche Details.",
        "options": "A) Als unvollstaendig markieren; B) aus weiteren Polarstern-Quellen nachergaenzen.",
        "recommended_option": "A",
        "why": "Die Zeile soll sichtbar bleiben, aber nicht mehr Vollstaendigkeit behaupten als vorhanden.",
        "blocking_or_non_blocking": "non-blocking",
    },
    {
        "question_id": "oq_007",
        "area": "Supporting pedagogy docs",
        "issue": "Die optional genannten Hintergrunddokumente waren im Workspace nicht vorhanden.",
        "options": "A) Nur mit Workbook plus Stitch-Docs arbeiten; B) spaeter konservative Nachvalidierung mit den Fachdokumenten machen.",
        "recommended_option": "B",
        "why": "Die aktuelle Struktur steht, kann aber durch spaetere Validierung noch stabiler werden.",
        "blocking_or_non_blocking": "non-blocking",
    },
]


@dataclass
class SourceMethod:
    legacy_row_id: str
    raw_number: str
    name: str
    one_sentence_description: str
    description: str
    purpose: str
    group_form: str
    time_estimate: str
    materials: str
    notes: str
    raw_tags: list[str]
    method_id: str


@dataclass
class SheetSpec:
    name: str
    rows: list[list[Any]]
    freeze_header: bool = True


class SimpleXlsxWriter:
    def __init__(self) -> None:
        self.sheets: list[SheetSpec] = []

    def add_sheet(self, name: str, rows: list[list[Any]], freeze_header: bool = True) -> None:
        self.sheets.append(SheetSpec(name=name, rows=rows, freeze_header=freeze_header))

    def save(self, path: Path) -> None:
        with ZipFile(path, "w", ZIP_DEFLATED) as zf:
            zf.writestr("[Content_Types].xml", self._content_types_xml())
            zf.writestr("_rels/.rels", self._root_rels_xml())
            zf.writestr("docProps/app.xml", self._app_xml())
            zf.writestr("docProps/core.xml", self._core_xml())
            zf.writestr("xl/workbook.xml", self._workbook_xml())
            zf.writestr("xl/_rels/workbook.xml.rels", self._workbook_rels_xml())
            zf.writestr("xl/styles.xml", self._styles_xml())
            for index, sheet in enumerate(self.sheets, start=1):
                zf.writestr(f"xl/worksheets/sheet{index}.xml", self._sheet_xml(sheet))

    def _content_types_xml(self) -> str:
        overrides = [
            '<Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
            '<Override PartName="/xl/styles.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>',
            '<Override PartName="/docProps/core.xml" '
            'ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>',
            '<Override PartName="/docProps/app.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>',
        ]
        for index in range(1, len(self.sheets) + 1):
            overrides.append(
                f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            )
        body = "".join(overrides)
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            f"{body}"
            "</Types>"
        )

    def _root_rels_xml(self) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="xl/workbook.xml"/>'
            '<Relationship Id="rId2" '
            'Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" '
            'Target="docProps/core.xml"/>'
            '<Relationship Id="rId3" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" '
            'Target="docProps/app.xml"/>'
            "</Relationships>"
        )

    def _app_xml(self) -> str:
        titles = "".join(f"<vt:lpstr>{escape(sheet.name)}</vt:lpstr>" for sheet in self.sheets)
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
            'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
            "<Application>Codex</Application>"
            f"<TitlesOfParts><vt:vector size=\"{len(self.sheets)}\" baseType=\"lpstr\">{titles}</vt:vector></TitlesOfParts>"
            f"<HeadingPairs><vt:vector size=\"2\" baseType=\"variant\">"
            "<vt:variant><vt:lpstr>Worksheets</vt:lpstr></vt:variant>"
            f"<vt:variant><vt:i4>{len(self.sheets)}</vt:i4></vt:variant>"
            "</vt:vector></HeadingPairs>"
            "</Properties>"
        )

    def _core_xml(self) -> str:
        now = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" '
            'xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            "<dc:creator>Codex</dc:creator>"
            "<cp:lastModifiedBy>Codex</cp:lastModifiedBy>"
            "<dc:title>Methodensammlung SSOT</dc:title>"
            f"<dcterms:created xsi:type=\"dcterms:W3CDTF\">{now}</dcterms:created>"
            f"<dcterms:modified xsi:type=\"dcterms:W3CDTF\">{now}</dcterms:modified>"
            "</cp:coreProperties>"
        )

    def _workbook_xml(self) -> str:
        sheets_xml = []
        for index, sheet in enumerate(self.sheets, start=1):
            sheets_xml.append(
                f'<sheet name="{escape(sheet.name)}" sheetId="{index}" r:id="rId{index + 1}"/>'
            )
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            "<workbookPr/>"
            "<bookViews><workbookView activeTab=\"0\"/></bookViews>"
            f"<sheets>{''.join(sheets_xml)}</sheets>"
            "<calcPr calcId=\"191029\"/>"
            "</workbook>"
        )

    def _workbook_rels_xml(self) -> str:
        rels = [
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
            'Target="styles.xml"/>'
        ]
        for index in range(1, len(self.sheets) + 1):
            rels.append(
                f'<Relationship Id="rId{index + 1}" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                f'Target="worksheets/sheet{index}.xml"/>'
            )
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f"{''.join(rels)}"
            "</Relationships>"
        )

    def _styles_xml(self) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            "<fonts count=\"2\">"
            "<font><sz val=\"11\"/><name val=\"Calibri\"/></font>"
            "<font><b/><sz val=\"11\"/><name val=\"Calibri\"/></font>"
            "</fonts>"
            "<fills count=\"2\">"
            "<fill><patternFill patternType=\"none\"/></fill>"
            "<fill><patternFill patternType=\"solid\"><fgColor rgb=\"FFECE1D9\"/><bgColor indexed=\"64\"/></patternFill></fill>"
            "</fills>"
            "<borders count=\"1\"><border><left/><right/><top/><bottom/><diagonal/></border></borders>"
            '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
            '<cellXfs count="3">'
            '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1">'
            '<alignment vertical="top" wrapText="1"/>'
            "</xf>"
            '<xf numFmtId="0" fontId="1" fillId="1" borderId="0" xfId="0" applyFont="1" applyFill="1" applyAlignment="1">'
            '<alignment vertical="top" wrapText="1"/>'
            "</xf>"
            '<xf numFmtId="1" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1" applyAlignment="1">'
            '<alignment vertical="top"/>'
            "</xf>"
            "</cellXfs>"
            '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
            "</styleSheet>"
        )

    def _sheet_xml(self, sheet: SheetSpec) -> str:
        max_cols = max((len(row) for row in sheet.rows), default=0)
        data_rows = []
        for row_index, row in enumerate(sheet.rows, start=1):
            cells = []
            for col_index, value in enumerate(row, start=1):
                if value is None or value == "":
                    continue
                cell_ref = f"{col_num_to_name(col_index)}{row_index}"
                style_id = "1" if row_index == 1 else "0"
                if is_number(value):
                    numeric = normalize_numeric(value)
                    numeric_style = "2" if float(numeric).is_integer() else "0"
                    cells.append(f'<c r="{cell_ref}" s="{numeric_style}"><v>{numeric}</v></c>')
                else:
                    text = escape(str(value))
                    cells.append(
                        f'<c r="{cell_ref}" s="{style_id}" t="inlineStr"><is><t xml:space="preserve">{text}</t></is></c>'
                    )
            data_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')
        col_xml = build_col_widths_xml(sheet.rows, max_cols)
        freeze = (
            '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" '
            'activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
            if sheet.freeze_header
            else '<sheetViews><sheetView workbookViewId="0"/></sheetViews>'
        )
        auto_filter = ""
        if sheet.rows and max_cols:
            last_ref = f"{col_num_to_name(max_cols)}{len(sheet.rows)}"
            auto_filter = f'<autoFilter ref="A1:{last_ref}"/>'
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            "<sheetPr/>"
            f"{freeze}"
            '<sheetFormatPr defaultRowHeight="15"/>'
            f"{col_xml}"
            f"<sheetData>{''.join(data_rows)}</sheetData>"
            f"{auto_filter}"
            "</worksheet>"
        )


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def normalize_numeric(value: Any) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isfinite(value):
            if value.is_integer():
                return str(int(value))
            return repr(value)
    return str(value)


def build_col_widths_xml(rows: list[list[Any]], max_cols: int) -> str:
    if max_cols == 0:
        return ""
    cols = []
    for index in range(1, max_cols + 1):
        max_len = 8
        for row in rows[: min(len(rows), 500)]:
            if len(row) < index:
                continue
            value = row[index - 1]
            if value in (None, ""):
                continue
            cell_len = max(len(part) for part in str(value).splitlines())
            max_len = max(max_len, cell_len)
        width = min(max(max_len * 1.08, 8), 60)
        cols.append(f'<col min="{index}" max="{index}" width="{width:.2f}" customWidth="1"/>')
    return f"<cols>{''.join(cols)}</cols>"


def col_num_to_name(index: int) -> str:
    name = []
    while index > 0:
        index, rem = divmod(index - 1, 26)
        name.append(chr(65 + rem))
    return "".join(reversed(name))


def clean_text(value: str, keep_newlines: bool = True) -> str:
    if value is None:
        return ""
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = value.replace("\u00a0", " ")
    if keep_newlines:
        lines = [" ".join(line.split()) for line in value.split("\n")]
        return "\n".join(line for line in lines).strip()
    return " ".join(value.split()).strip()


def clean_single_line(value: str) -> str:
    return clean_text(value, keep_newlines=False)


def normalize_legacy_id(raw_value: str) -> str:
    value = clean_single_line(raw_value)
    if value.endswith(".0"):
        value = value[:-2]
    return value


def parse_shared_strings(zf: ZipFile) -> list[str]:
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    out = []
    for si in root.findall("a:si", NS_MAIN):
        direct = si.find("a:t", NS_MAIN)
        if direct is not None:
            out.append(direct.text or "")
            continue
        text_parts = []
        for run in si.findall("a:r", NS_MAIN):
            node = run.find("a:t", NS_MAIN)
            if node is not None:
                text_parts.append(node.text or "")
        out.append("".join(text_parts))
    return out


def col_name_to_index(name: str) -> int:
    total = 0
    for char in name:
        total = total * 26 + ord(char) - 64
    return total


def parse_sheet_rows(zf: ZipFile, sheet_name: str, shared_strings: list[str]) -> list[list[str]]:
    root = ET.fromstring(zf.read(sheet_name))
    sheet_data = root.find("a:sheetData", NS_MAIN)
    rows: list[list[str]] = []
    if sheet_data is None:
        return rows
    for row in sheet_data.findall("a:row", NS_MAIN):
        values: dict[int, str] = {}
        for cell in row.findall("a:c", NS_MAIN):
            ref = cell.attrib["r"]
            col_name = "".join(ch for ch in ref if ch.isalpha())
            idx = col_name_to_index(col_name)
            cell_type = cell.attrib.get("t")
            value_node = cell.find("a:v", NS_MAIN)
            inline_node = cell.find("a:is", NS_MAIN)
            value = ""
            if cell_type == "s" and value_node is not None:
                value = shared_strings[int(value_node.text)]
            elif cell_type == "inlineStr" and inline_node is not None:
                value = "".join(node.text or "" for node in inline_node.iterfind(".//a:t", NS_MAIN))
            elif value_node is not None and value_node.text is not None:
                value = value_node.text
            values[idx] = value
        max_col = max(values, default=0)
        rows.append([values.get(index, "") for index in range(1, max_col + 1)])
    return rows


def load_source_methods(source_path: Path) -> tuple[list[list[str]], list[SourceMethod]]:
    with ZipFile(source_path) as zf:
        shared = parse_shared_strings(zf)
        rows = parse_sheet_rows(zf, "xl/worksheets/sheet1.xml", shared)
    if not rows:
        raise RuntimeError("Source workbook contains no rows.")
    raw_rows = [(row + [""] * len(RAW_HEADERS))[: len(RAW_HEADERS)] for row in rows]
    methods: list[SourceMethod] = []
    for row in raw_rows[1:]:
        if not any(clean_single_line(cell) for cell in row):
            continue
        legacy = normalize_legacy_id(row[0])
        method_id = f"m{int(legacy):03d}"
        methods.append(
            SourceMethod(
                legacy_row_id=legacy,
                raw_number=row[0],
                name=clean_text(row[1]),
                one_sentence_description=clean_text(row[2]),
                description=clean_text(row[3]),
                purpose=clean_text(row[4]),
                group_form=clean_text(row[5]),
                time_estimate=clean_text(row[6]),
                materials=clean_text(row[7]),
                notes=clean_text(row[8]),
                raw_tags=[clean_text(value) for value in row[9:14] if clean_single_line(value)],
                method_id=method_id,
            )
        )
    return raw_rows, methods


def normalized_name(value: str) -> str:
    lines = [clean_single_line(line) for line in clean_text(value).split("\n") if clean_single_line(line)]
    return " / ".join(lines)


def short_description(method: SourceMethod) -> str:
    if method.one_sentence_description:
        return clean_single_line(method.one_sentence_description)
    desc = clean_text(method.description)
    if not desc:
        return ""
    first_line = clean_single_line(desc.split("\n")[0])
    sentence = re.split(r"(?<=[.!?])\s+", first_line, maxsplit=1)[0]
    sentence = clean_single_line(sentence)
    if len(sentence) > 190:
        sentence = sentence[:187].rstrip() + "..."
    return sentence


def build_keyword_blob(method: SourceMethod) -> str:
    parts = [method.name, method.one_sentence_description, method.description, method.purpose, method.group_form, method.materials, method.notes]
    parts.extend(method.raw_tags)
    blob = " \n ".join(clean_text(part, keep_newlines=False) for part in parts if part)
    blob = blob.lower()
    blob = blob.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return blob


def extract_group_size(method: SourceMethod) -> tuple[Any, Any, list[str]]:
    text = build_keyword_blob(method)
    notes = []
    min_size: Any = ""
    max_size: Any = ""
    match = re.search(r"mind\.\s*(\d+)\s*tn", text)
    if match:
        min_size = int(match.group(1))
        notes.append(f"Gruppengroesse mind. {min_size} TN explizit genannt.")
    match = re.search(r"max\.\s*(\d+)\s*tn", text)
    if match:
        max_size = int(match.group(1))
        notes.append(f"Gruppengroesse max. {max_size} TN explizit genannt.")
    match = re.search(r"gruppen von vier bis fuenf spielern|gruppen von vier bis fünf spielern", text)
    if match:
        min_size = 4
        max_size = 5
        notes.append("Gruppengroesse 4-5 Personen explizit genannt.")
    match = re.search(r"(\d+)-(\d+)\s*personen", text)
    if match:
        min_size = int(match.group(1))
        max_size = int(match.group(2))
        notes.append(f"Gruppengroesse {min_size}-{max_size} Personen explizit genannt.")
    match = re.search(r"(\d+)er[- ]teams", text)
    if match:
        value = int(match.group(1))
        min_size = value
        max_size = value
        notes.append(f"Arbeit in {value}er-Teams explizit genannt.")
    match = re.search(r"kreisen zu (\d+)-(\d+) personen", text)
    if match:
        min_size = int(match.group(1))
        max_size = int(match.group(2))
        notes.append(f"Kreisgroesse {min_size}-{max_size} Personen explizit genannt.")
    if method.legacy_row_id in METHOD_OVERRIDES:
        override = METHOD_OVERRIDES[method.legacy_row_id]
        min_size = override.get("group_size_min", min_size)
        max_size = override.get("group_size_max", max_size)
    return min_size, max_size, notes


def infer_duration(method: SourceMethod) -> tuple[Any, Any, list[str]]:
    if method.legacy_row_id in METHOD_OVERRIDES:
        override = METHOD_OVERRIDES[method.legacy_row_id]
        if "duration_min" in override or "duration_max" in override:
            return override.get("duration_min", ""), override.get("duration_max", ""), list(override.get("source_notes", []))
    text = " \n ".join([method.time_estimate, method.description, method.notes])
    text_l = build_keyword_blob(method)
    notes: list[str] = []
    if method.time_estimate:
        range_match = re.search(r"(\d+)\s*[-–]\s*(\d+)\s*min", text_l)
        if range_match:
            start = int(range_match.group(1))
            end = int(range_match.group(2))
            notes.append(f"Dauer {start}-{end} Minuten aus Time Estimate extrahiert.")
            return start, end, notes
        minutes_match = re.search(r"(\d+)\s*min(?:ute[n]?)?", text_l)
        if minutes_match:
            value = int(minutes_match.group(1))
            notes.append(f"Dauer {value} Minuten aus Time Estimate extrahiert.")
            return value, value, notes
    return "", "", notes


def infer_energy(method: SourceMethod) -> tuple[str, str]:
    blob = build_keyword_blob(method)
    if any(keyword in blob for keyword in ["aktivierung", "auflockerung", "bewegung", "outdoor", "teamspiel"]):
        return "hoch", "HEURISTIC_KEYWORD_MAPPING"
    if any(keyword in blob for keyword in ["entspannung", "ruhe", "cool-down", "body-scan", "körperreise", "achtsamkeit"]):
        return "niedrig", "HEURISTIC_KEYWORD_MAPPING"
    return "mittel", "HEURISTIC_KEYWORD_MAPPING"


def infer_intensity(method: SourceMethod) -> tuple[str, str]:
    blob = build_keyword_blob(method)
    if any(keyword in blob for keyword in ["vertrauen", "feedback", "gefuehl", "gefühl", "stress", "kritik", "soziale", "selbstheilung", "anstrengung"]):
        return "hoch", "HEURISTIC_KEYWORD_MAPPING"
    if any(keyword in blob for keyword in ["selbstwahrnehmung", "ressourcen", "stärken", "staerken", "zukunft", "entscheidung"]):
        return "mittel", "HEURISTIC_KEYWORD_MAPPING"
    return "niedrig", "HEURISTIC_KEYWORD_MAPPING"


def infer_movement(method: SourceMethod) -> tuple[str, str]:
    blob = build_keyword_blob(method)
    if any(
        keyword in blob
        for keyword in [
            "aktivierung und bewegung",
            "bewegungsfoerdernd",
            "bewegungsfördernd",
            "im raum herum",
            "spazieren durch den raum",
            "bewegen sich",
            "platz tauschen",
            "outdoor",
            "obstsalat",
            "aufstellen",
            "stuehle kippen",
            "stühle kippen",
        ]
    ):
        return "hoch", "HEURISTIC_KEYWORD_MAPPING"
    if any(
        keyword in blob
        for keyword in [
            "sitzkreis",
            "papier",
            "zeichnen",
            "schliesst die augen",
            "schließt die augen",
            "bequem sitzt",
            "liegt",
            "liegst",
            "großes blatt",
            "grosses blatt",
            "arbeitsblatt",
        ]
    ):
        return "niedrig", "HEURISTIC_KEYWORD_MAPPING"
    return "mittel", "HEURISTIC_KEYWORD_MAPPING"


def infer_noise(method: SourceMethod) -> tuple[str, str]:
    blob = build_keyword_blob(method)
    if any(
        keyword in blob
        for keyword in [
            "auflockerung",
            "aktivierung",
            "orchester",
            "body percussion",
            "klatschspiel",
            "klatschen",
            "schnick-schnack",
            "hai-attacke",
            "fauchgeräusch",
            "fauchgeraeusch",
        ]
    ):
        return "hoch", "HEURISTIC_KEYWORD_MAPPING"
    if any(
        keyword in blob
        for keyword in [
            "still",
            "stille",
            "ruhig",
            "achtsamkeit",
            "koerperreise",
            "körperreise",
            "body-scan",
            "rosinen-uebung",
            "rosinen-übung",
            "augen schließen",
            "augen schliessen",
        ]
    ):
        return "niedrig", "HEURISTIC_KEYWORD_MAPPING"
    return "mittel", "HEURISTIC_KEYWORD_MAPPING"


def infer_indoor_outdoor(method: SourceMethod) -> tuple[str, str]:
    blob = build_keyword_blob(method)
    if "outdoor" in blob or "park" in blob:
        return "aussen", "DESCRIPTION_EXPLICIT"
    if any(keyword in blob for keyword in ["tafel", "whiteboard", "sitzkreis", "klassenzimmer"]):
        return "innen", "DESCRIPTION_EXPLICIT"
    if "raum" in blob:
        return "innen", "HEURISTIC_KEYWORD_MAPPING"
    return "", ""


def infer_preparation(method: SourceMethod) -> tuple[str, str]:
    materials = clean_single_line(method.materials).lower()
    description = build_keyword_blob(method)
    if any(keyword in materials for keyword in ["arbeitsblatt", "tier-bilder", "tier bilder", "maßband", "massband", "murmeln", "spaghetti", "marshmell", "holz", "eier", "ei "]):
        return "hoch", "RAW_IMPORT"
    if any(keyword in materials for keyword in ["papier", "stifte", "karten", "tafel", "timer", "stofftier", "gummib", "schwamm"]) or materials:
        return "mittel", "RAW_IMPORT"
    if any(keyword in description for keyword in ["karteikarten", "plakat", "grosses blatt", "großes blatt", "arbeitsblatt"]):
        return "mittel", "DESCRIPTION_EXPLICIT"
    return "gering", "HEURISTIC_KEYWORD_MAPPING"


def infer_safeguarding(method: SourceMethod) -> tuple[str, str]:
    blob = build_keyword_blob(method)
    if any(
        keyword in blob
        for keyword in [
            "achtung",
            "schliesst die augen",
            "schließt die augen",
            "augen schliessen",
            "augen schließen",
            "fallen",
            "rueckwaerts",
            "rückwärts",
            "nicht zu weit",
            "covid",
        ]
    ):
        return "ja", "DESCRIPTION_EXPLICIT"
    if any(
        keyword in blob
        for keyword in [
            "vertrauen",
            "feedback",
            "gefuehl",
            "gefühl",
            "stress",
            "kritik",
            "hilfe",
            "selbstheilung",
        ]
    ):
        return "ja", "HEURISTIC_KEYWORD_MAPPING"
    return "", ""


def infer_status(method: SourceMethod) -> str:
    override = METHOD_OVERRIDES.get(method.legacy_row_id, {})
    if "status" in override:
        return override["status"]
    if not method.description and not method.purpose:
        return "unvollstaendig"
    return "aktiv"


def derive_matches(blob: str, rules: list[tuple[str, list[str]]]) -> list[str]:
    matches = []
    for label, keywords in rules:
        if any(keyword in blob for keyword in keywords):
            matches.append(label)
    return matches


def primary_phase_for_method(method: SourceMethod) -> str:
    phases = derive_matches(build_keyword_blob(method), PHASE_RULES)
    if not phases:
        return "Vertiefen"
    priority = {
        "Ankommen": 1,
        "Aktivieren": 2,
        "Fokussieren": 3,
        "Beruhigen": 4,
        "Reflektieren": 5,
        "Abschluss": 6,
        "Ueberleitung": 7,
        "Vertiefen": 8,
    }
    return sorted(phases, key=lambda value: priority.get(value, 99))[0]


def energy_role_from_phase(phase: str) -> str:
    mapping = {
        "Ankommen": "starten",
        "Aktivieren": "aktivieren",
        "Fokussieren": "fokussieren",
        "Beruhigen": "beruhigen",
        "Reflektieren": "abschliessen",
        "Abschluss": "abschliessen",
        "Ueberleitung": "ueberleiten",
        "Vertiefen": "vertiefen",
    }
    return mapping.get(phase, "vertiefen")


def duration_display(duration_min: Any, duration_max: Any) -> str:
    if duration_min and duration_max:
        if duration_min == duration_max:
            return f"{duration_min} Min."
        return f"{duration_min}-{duration_max} Min."
    if duration_min:
        return f"ab {duration_min} Min."
    if duration_max:
        return f"bis {duration_max} Min."
    return ""


def split_fragments(value: str) -> list[str]:
    if not value:
        return []
    value = clean_text(value, keep_newlines=True)
    parts = re.split(r"[,/;]|\n", value)
    out = []
    for part in parts:
        cleaned = clean_single_line(part)
        if cleaned:
            out.append(cleaned)
    return out


def split_purpose_fragments(value: str) -> list[str]:
    if not value:
        return []
    value = clean_text(value, keep_newlines=True)
    parts = re.split(r"[,;]|\n", value)
    out = []
    for part in parts:
        cleaned = clean_single_line(part)
        if cleaned:
            out.append(cleaned)
    return out


def primary_purpose_from_raw(method: SourceMethod) -> tuple[str, list[str]]:
    fragments = split_purpose_fragments(method.purpose)
    if not fragments:
        return "", []
    notes: list[str] = []
    if len(fragments) > 1:
        notes.append(
            "Mehrfach-Purpose im Import; primary_purpose konservativ auf das erste Rohfragment reduziert. Weitere Signale liegen in Method_Tags als purpose_signal."
        )
    return fragments[0], notes


def confidence_to_text(value: float) -> str:
    return f"{value:.2f}"


def reason_for_collection(method: dict[str, Any], collection_id: str) -> str:
    title = method["name_de"]
    vector_labels = method.get("vector_names", [])
    if collection_id == "col_ankommen":
        return "Deutliche Warm-up- oder Kennenlern-Signale im Rohmaterial."
    if collection_id == "col_fokus":
        return "Achtsamkeit, Konzentration oder Beruhigung sind klar markiert."
    if collection_id == "col_gefuehle":
        return "Bezieht sich explizit auf Gefuehle, Befindlichkeit oder Beziehung."
    if collection_id == "col_staerken":
        return "Staerken-, Ressourcen- oder Selbstvertrauensbezug ist im Import klar sichtbar."
    if collection_id == "col_kooperation":
        return "Kooperation, Gruppendynamik oder Vertrauen stehen im Vordergrund."
    if collection_id == "col_zukunft":
        return "Die Methode bearbeitet Zukunft, Entscheidungen oder partizipative Planung."
    if collection_id == "col_reflexion":
        return "Die Methode eignet sich fuer Feedback, Rueckblick oder Abschluss."
    return f"Passend zu {', '.join(vector_labels) if vector_labels else title}."


def build_methods_sheet(methods: list[SourceMethod]) -> tuple[list[list[Any]], dict[str, dict[str, Any]]]:
    duplicate_names = defaultdict(list)
    for method in methods:
        duplicate_names[normalized_name(method.name)].append(method.legacy_row_id)

    rows = [METHOD_HEADERS]
    method_index: dict[str, dict[str, Any]] = {}

    for method in methods:
        duration_min, duration_max, duration_notes = infer_duration(method)
        group_min, group_max, group_notes = extract_group_size(method)
        primary_purpose, purpose_notes = primary_purpose_from_raw(method)
        energy_level, energy_source = infer_energy(method)
        intensity, intensity_source = infer_intensity(method)
        movement_level, movement_source = infer_movement(method)
        noise_level, noise_source = infer_noise(method)
        indoor_outdoor, indoor_outdoor_source = infer_indoor_outdoor(method)
        preparation_level, preparation_source = infer_preparation(method)
        safeguarding_flag, safeguarding_source = infer_safeguarding(method)
        override = METHOD_OVERRIDES.get(method.legacy_row_id, {})
        source_notes = duration_notes + group_notes + purpose_notes + list(override.get("source_notes", []))
        uncertainty_flag = override.get("uncertainty_flag", "")
        uncertainty_note = override.get("uncertainty_note", "")

        if len(duplicate_names[normalized_name(method.name)]) > 1 and not uncertainty_flag:
            uncertainty_flag = "ja"
            uncertainty_note = "Doppelter Methodentitel im Import; Datensatz vorsorglich nicht zusammengefuehrt."

        row = {
            "method_id": method.method_id,
            "legacy_row_id": method.legacy_row_id,
            "name_de": normalized_name(method.name),
            "short_description": short_description(method),
            "full_description": method.description,
            "primary_purpose": primary_purpose,
            "group_form": clean_single_line(method.group_form),
            "duration_min": duration_min,
            "duration_max": duration_max,
            "materials": clean_text(method.materials),
            "facilitator_notes": clean_text(method.notes),
            "source_notes": " | ".join(dict.fromkeys(note for note in source_notes if note)),
            "age_min": "",
            "age_max": "",
            "group_size_min": group_min,
            "group_size_max": group_max,
            "energy_level": energy_level,
            "energy_level_source": energy_source,
            "intensity": intensity,
            "intensity_source": intensity_source,
            "movement_level": movement_level,
            "movement_level_source": movement_source,
            "noise_level": noise_level,
            "noise_level_source": noise_source,
            "indoor_outdoor": indoor_outdoor,
            "indoor_outdoor_source": indoor_outdoor_source,
            "preparation_level": preparation_level,
            "preparation_level_source": preparation_source,
            "safeguarding_flag": safeguarding_flag,
            "safeguarding_flag_source": safeguarding_source,
            "status": infer_status(method),
            "uncertainty_flag": uncertainty_flag,
            "uncertainty_note": uncertainty_note,
        }
        method_index[method.method_id] = row
        rows.append([row[header] for header in METHOD_HEADERS])
    return rows, method_index


def method_tag_entries(method: SourceMethod, method_row: dict[str, Any], vector_names_by_id: dict[str, str]) -> list[list[Any]]:
    entries: list[list[Any]] = []
    raw_tag_cells = method.raw_tags
    for raw_tag in raw_tag_cells:
        entries.append([method.method_id, "raw_tag", raw_tag, "RAW_IMPORT:Tag1-Tag5", confidence_to_text(1.0)])
    purpose_fragments = split_purpose_fragments(method.purpose)
    for fragment in purpose_fragments[1:]:
        entries.append([method.method_id, "purpose_signal", fragment, "RAW_IMPORT:Purpose", confidence_to_text(1.0)])

    blob = build_keyword_blob(method)

    for topic, keywords in TOPIC_RULES:
        if any(keyword in blob for keyword in keywords):
            entries.append([method.method_id, "topic", topic, "NEW_CONTROLLED_TAXONOMY:topic", confidence_to_text(0.85)])

    for skill, keywords in SKILL_RULES:
        if any(keyword in blob for keyword in keywords):
            entries.append([method.method_id, "skill", skill, "NEW_CONTROLLED_TAXONOMY:skill", confidence_to_text(0.85)])

    for phase, keywords in PHASE_RULES:
        if any(keyword in blob for keyword in keywords):
            entries.append([method.method_id, "phase", phase, "NEW_CONTROLLED_TAXONOMY:phase", confidence_to_text(0.8)])

    for use_case, keywords in USE_CASE_RULES:
        if any(keyword in blob for keyword in keywords):
            entries.append([method.method_id, "use_case", use_case, "NEW_CONTROLLED_TAXONOMY:use_case", confidence_to_text(0.8)])

    vector_matches = derive_vectors(method)
    for vector_id, confidence, _note in vector_matches:
        entries.append([method.method_id, "vector", vector_names_by_id[vector_id], "NEW_CONTROLLED_TAXONOMY:vector", confidence_to_text(confidence)])

    collection_candidates = suggest_collection_ids(vector_matches)
    for collection_id in collection_candidates:
        entries.append([method.method_id, "collection_candidate", collection_id, "NEW_CONTROLLED_TAXONOMY:collection", confidence_to_text(0.75)])

    unique = []
    seen = set()
    for entry in entries:
        key = tuple(entry)
        if key not in seen:
            seen.add(key)
            unique.append(entry)
    return unique


def derive_vectors(method: SourceMethod) -> list[tuple[str, float, str]]:
    blob = build_keyword_blob(method)
    matches: list[tuple[str, float, str]] = []
    for rule in VECTOR_RULES:
        if any(keyword in blob for keyword in rule["keywords"]):
            matches.append((rule["vector_id"], rule["confidence"], "Keyword-Mapping aus Rohfeldern"))
    deduped: dict[str, tuple[str, float, str]] = {}
    for vector_id, confidence, note in matches:
        if vector_id not in deduped or confidence > deduped[vector_id][1]:
            deduped[vector_id] = (vector_id, confidence, note)
    return list(deduped.values())


def suggest_collection_ids(vector_matches: list[tuple[str, float, str]]) -> list[str]:
    vector_ids = {vector_id for vector_id, _confidence, _note in vector_matches}
    collection_ids = []
    mapping = {
        "vector_ankommen": "col_ankommen",
        "vector_fokus": "col_fokus",
        "vector_entspannung": "col_fokus",
        "vector_gefuehle": "col_gefuehle",
        "vector_staerken": "col_staerken",
        "vector_kooperation": "col_kooperation",
        "vector_zukunft": "col_zukunft",
        "vector_reflexion": "col_reflexion",
    }
    for vector_id in vector_ids:
        collection_id = mapping.get(vector_id)
        if collection_id and collection_id not in collection_ids:
            collection_ids.append(collection_id)
    return collection_ids


def build_method_tags_and_vector_map(
    source_methods: list[SourceMethod],
    method_index: dict[str, dict[str, Any]],
) -> tuple[list[list[Any]], list[list[Any]], dict[str, list[str]]]:
    method_tags_rows = [METHOD_TAG_HEADERS]
    method_vector_rows = [METHOD_VECTOR_HEADERS]
    vector_names_by_id = {vector["vector_id"]: vector["vector_name_de"] for vector in VECTOR_DEFINITIONS}
    vector_map_labels: dict[str, list[str]] = {}

    for method in source_methods:
        method_row = method_index[method.method_id]
        vector_matches = derive_vectors(method)
        vector_map_labels[method.method_id] = [vector_names_by_id[vector_id] for vector_id, _confidence, _note in vector_matches]
        for entry in method_tag_entries(method, method_row, vector_names_by_id):
            method_tags_rows.append(entry)
        for vector_id, confidence, note in vector_matches:
            method_vector_rows.append([method.method_id, vector_id, confidence_to_text(confidence), note])
    return method_tags_rows, method_vector_rows, vector_map_labels


def build_variants_sheet() -> tuple[list[list[Any]], dict[str, dict[str, Any]]]:
    rows = [VARIANT_HEADERS]
    index: dict[str, dict[str, Any]] = {}
    for variant in VARIANT_DEFINITIONS:
        index[variant["variant_id"]] = variant
        rows.append([variant[header] for header in VARIANT_HEADERS])
    return rows, index


def build_finder_sheet() -> list[list[Any]]:
    rows = [FINDER_HEADERS]
    for item in FINDER_INTENTS:
        rows.append([item[header] for header in FINDER_HEADERS])
    return rows


def build_collections_sheet() -> list[list[Any]]:
    rows = [COLLECTION_HEADERS]
    for collection in COLLECTIONS:
        rows.append([collection[header] for header in COLLECTION_HEADERS])
    return rows


def build_collection_items(
    source_methods: list[SourceMethod],
    method_index: dict[str, dict[str, Any]],
) -> list[list[Any]]:
    rows = [COLLECTION_ITEM_HEADERS]
    vector_matches_by_method = {method.method_id: {vector_id for vector_id, _c, _n in derive_vectors(method)} for method in source_methods}

    for collection in COLLECTIONS:
        candidates = []
        for method in source_methods:
            method_row = method_index[method.method_id]
            method_vectors = vector_matches_by_method[method.method_id]
            if any(vector_id in method_vectors for vector_id in collection["vectors"]):
                completeness = 0
                if method_row["short_description"]:
                    completeness += 1
                if method_row["full_description"]:
                    completeness += 1
                if method_row["materials"]:
                    completeness += 1
                if method_row["facilitator_notes"]:
                    completeness += 1
                candidates.append((completeness, int(method.legacy_row_id), method))
        candidates.sort(key=lambda item: (-item[0], item[1]))
        for sort_order, (_score, _legacy, method) in enumerate(candidates[:10], start=1):
            rows.append(
                [
                    collection["collection_id"],
                    method.method_id,
                    "method",
                    sort_order,
                    reason_for_collection(method_index[method.method_id], collection["collection_id"]),
                ]
            )
    return rows


def icon_hint(method_row: dict[str, Any], vector_labels: list[str]) -> str:
    joined = " | ".join(vector_labels).lower()
    if "staerken" in joined or "ressourcen" in joined:
        return "stern"
    if "gefuehle" in joined:
        return "herz"
    if "zukunft" in joined:
        return "kompass"
    if "kooperation" in joined or "vertrauen" in joined:
        return "gruppe"
    if "achtsamkeit" in joined or "entspannung" in joined:
        return "blatt"
    if "aktivierung" in joined:
        return "bewegung"
    if "reflexion" in joined:
        return "sprechblase"
    return "karte"


def build_composer_reference(
    source_methods: list[SourceMethod],
    method_index: dict[str, dict[str, Any]],
    variant_index: dict[str, dict[str, Any]],
    vector_map_labels: dict[str, list[str]],
) -> list[list[Any]]:
    rows = [COMPOSER_HEADERS]
    for method in source_methods:
        method_row = method_index[method.method_id]
        phase = primary_phase_for_method(method)
        vector_labels = vector_map_labels.get(method.method_id, [])
        method_row["vector_names"] = vector_labels
        summary = method_row["short_description"] or clean_single_line(method.description)
        searchable = " | ".join(
            item
            for item in [
                method_row["name_de"],
                summary,
                method_row["primary_purpose"],
                method_row["materials"],
                " | ".join(method.raw_tags),
                " | ".join(vector_labels),
            ]
            if item
        )
        filter_text = " | ".join(item for item in [phase, method_row["group_form"], method_row["energy_level"], *vector_labels] if item)
        rows.append(
            [
                f"block_{method.method_id}",
                "method",
                method.method_id,
                method_row["name_de"],
                duration_display(method_row["duration_min"], method_row["duration_max"]),
                summary,
                phase,
                energy_role_from_phase(phase),
                icon_hint(method_row, vector_labels),
                method_row["group_form"],
                method_row["materials"],
                searchable,
                filter_text,
                "ja",
            ]
        )
    for variant_id, variant in variant_index.items():
        method_row = method_index[variant["method_id"]]
        variant_duration_display = variant["recommended_duration"] or duration_display(method_row["duration_min"], method_row["duration_max"])
        searchable = " | ".join(
            item
            for item in [
                variant["variant_label"],
                variant["composer_card_summary"],
                variant["use_case"],
                variant["social_setting"],
                method_row["name_de"],
            ]
            if item
        )
        filter_text = " | ".join(
            item
            for item in [variant["phase"], variant["energy_role"], variant["social_setting"], method_row["group_form"]]
            if item
        )
        rows.append(
            [
                f"block_{variant_id}",
                "variant",
                variant_id,
                f"{method_row['name_de']} - {variant['variant_label']}",
                variant_duration_display,
                variant["composer_card_summary"],
                variant["phase"],
                variant["energy_role"],
                icon_hint(method_row, method_row.get("vector_names", [])),
                variant["social_setting"],
                variant["materials_override"] or method_row["materials"],
                searchable,
                filter_text,
                "ja",
            ]
        )
    return rows


def build_ui_field_mapping() -> list[list[Any]]:
    rows = [UI_MAPPING_HEADERS]
    items = [
        {
            "screen": "Method Finder",
            "component": "Quick-start chips",
            "ui_label": "Situationsbasierte Einstiege",
            "source_sheet": "Finder_Intents",
            "source_field": "intent_label_de, user_need_statement, description",
            "transformation_rule": "Je Intent eine Finder-Kachel oder ein Chip.",
            "fallback_rule": "Wenn kein Intent passt, freien Problembeschrieb anbieten.",
            "notes": "Auf die Logik von entry_moment_situation_based_start.html abgestimmt; freie Texteingabe bleibt Runtime-Eingabe.",
        },
        {
            "screen": "Method Finder",
            "component": "Intent result ranking",
            "ui_label": "Empfohlene Methoden",
            "source_sheet": "Finder_Intents + Methods + Method_Variants",
            "source_field": "recommended_method_ids_or_variant_ids",
            "transformation_rule": "IDs auf Method- oder Variant-Datensaetze aufloesen und mit ranking_notes sortieren.",
            "fallback_rule": "Wenn empfohlene IDs fehlen, ueber Method_Tags.use_case und Method_Vector_Map aehnliche Treffer bilden.",
            "notes": "Keine fiktiven Finder-Kategorien aus Mockups einsetzen.",
        },
        {
            "screen": "Library",
            "component": "Method list cards",
            "ui_label": "Bibliothekskarte",
            "source_sheet": "Methods",
            "source_field": "name_de, short_description, duration_min, duration_max, group_form, materials, safeguarding_flag",
            "transformation_rule": "Dauer als Range rendern; Materialien nur als knappen Chip zeigen.",
            "fallback_rule": "Leere Felder ausblenden statt Platzhalter zu erfinden; Duration-Chips verbergen, wenn duration_min und duration_max leer sind.",
            "notes": "Auf library_editorial_collection.html abgestimmt. Chau Philomene One nur fuer editoriale Highlights; funktionale Karte in Roboto.",
        },
        {
            "screen": "Library",
            "component": "Browse vectors",
            "ui_label": "Thematische Vektoren",
            "source_sheet": "Vectors + Method_Vector_Map",
            "source_field": "vector_name_de, vector_definition",
            "transformation_rule": "Vektor als browsebare Dimension mit zugeordneten Methoden verwenden.",
            "fallback_rule": "Bei schwacher Zuordnung Confidence-Hinweis intern nutzen, aber UI klar halten.",
            "notes": "Sparse Browse-Dimensionen statt facettenreicher Filterwand.",
        },
        {
            "screen": "Library collection pages",
            "component": "Collection hero and list",
            "ui_label": "Kollektion",
            "source_sheet": "Collections + Collection_Items + Methods/Method_Variants",
            "source_field": "name_de, short_description, editorial_rationale, item lists",
            "transformation_rule": "Collection_Items sortiert aufloesen und jeweils Methode oder Variante laden.",
            "fallback_rule": "Wenn ein Item fehlt, Collection nicht mit Ersatzdaten auffuellen.",
            "notes": "Kollektionen sind kuratiert und nicht identisch mit Taxonomie.",
        },
        {
            "screen": "Method Detail",
            "component": "Header",
            "ui_label": "Titel, Kurzbeschreibung, Meta",
            "source_sheet": "Methods",
            "source_field": "name_de, short_description, duration_min, duration_max, group_form, materials",
            "transformation_rule": "Meta-Chips nur bei vorhandenen Werten zeigen.",
            "fallback_rule": "Fehlende Dauer oder Gruppengroesse nicht durch Standards ersetzen; Duration-Chips verbergen, wenn keine grounded duration vorliegt.",
            "notes": "Auf method_detail_the_human_mirror.html abgestimmt. Reale Methodentitel ueberschreiben Mockup-Platzhalter ausnahmslos.",
        },
        {
            "screen": "Method Detail",
            "component": "Operational guide",
            "ui_label": "Durchfuehrung",
            "source_sheet": "Methods",
            "source_field": "full_description",
            "transformation_rule": "Absatzweise oder in Schritte zerlegen, ohne neue Fachinhalte hinzuzufuegen.",
            "fallback_rule": "Wenn die Quelle knapp ist, Originaltext knapp und unveraendert zeigen.",
            "notes": "Nicht in pseudotherapeutische Sprache umschreiben.",
        },
        {
            "screen": "Method Detail",
            "component": "Facilitator notes",
            "ui_label": "Hinweise fuer Leitung",
            "source_sheet": "Methods + Method_Variants",
            "source_field": "facilitator_notes, facilitator_tip, risk_alert, safeguarding_flag",
            "transformation_rule": "Variant-spezifische Hinweise haben Vorrang vor Method-Basishinweisen.",
            "fallback_rule": "Wenn kein Hinweis vorhanden ist, Bereich ausblenden statt zu erfinden.",
            "notes": "Risk/Trust-Layer muss operational und plausibel bleiben.",
        },
        {
            "screen": "Composer method pool",
            "component": "Draggable pool cards",
            "ui_label": "Pool-Eintrag",
            "source_sheet": "Composer_Blocks_Reference",
            "source_field": "display_title, duration_display, card_summary, phase, energy_role",
            "transformation_rule": "Composer verwendet nur diese Helper-Sicht als Pool-Source.",
            "fallback_rule": "Ohne passenden Block keine implizite Runtime-Ableitung erfinden; Dauer im Pool nur zeigen, wenn duration_display befuellt ist.",
            "notes": "Auf workshop_composer_session_flow.html abgestimmt. Pool kann Methoden und Varianten gemeinsam anzeigen.",
        },
        {
            "screen": "Composer timeline blocks",
            "component": "Session block",
            "ui_label": "Zeitblock",
            "source_sheet": "Composer_Blocks_Reference + Methods + Method_Variants",
            "source_field": "block_ref_id, source_id, phase, energy_role",
            "transformation_rule": "Runtime speichert Session-Instanz getrennt; SSOT liefert nur referenzierbare Block-Basis.",
            "fallback_rule": "Custom Blocks muessen als Runtime-Objekte ausserhalb dieser SSOT entstehen; Timeline-Dauerlabels verbergen, wenn duration_display leer ist.",
            "notes": "Session blocks sind nicht identisch mit Methoden. Die Composer-Timeline folgt der Produktlogik aus workshop_composer_session_flow.html.",
        },
        {
            "screen": "Active Session",
            "component": "Current instruction",
            "ui_label": "Jetzt anleiten",
            "source_sheet": "Method_Variants + Methods",
            "source_field": "active_session_prompt, full_description",
            "transformation_rule": "Variant prompt zuerst, sonst kurze Passage aus full_description.",
            "fallback_rule": "Wenn beides fehlt, nur Titel plus Method Detail verlinken.",
            "notes": "Auf active_session_pro_facilitator_mode.html abgestimmt. Active Session zeigt eine konkrete Session-Instanz; Notizen und Timer sind Runtime-Daten.",
        },
        {
            "screen": "Active Session",
            "component": "Facilitator tip",
            "ui_label": "Moderationshinweis",
            "source_sheet": "Method_Variants + Methods",
            "source_field": "facilitator_tip, facilitator_notes",
            "transformation_rule": "Variant hint hat Vorrang; lange Notizen fuer die Session-Ansicht kuerzen.",
            "fallback_rule": "Wenn kein Hinweis vorliegt, Bereich ausblenden.",
            "notes": "Leitungshinweise duerfen nicht von Mockup-Patterns erfunden werden.",
        },
        {
            "screen": "Active Session",
            "component": "Risk alert",
            "ui_label": "Achtung",
            "source_sheet": "Method_Variants + Methods",
            "source_field": "risk_alert, safeguarding_flag, facilitator_notes",
            "transformation_rule": "Nur bei realer Quelle oder klarer Variant-Notiz als Alert ausgeben.",
            "fallback_rule": "Kein generischer Warntext, wenn die Quelle nichts hergibt.",
            "notes": "Passt zu Schul- und Workshoprealitaet; ersetzt kein paedagogisches Urteil.",
        },
        {
            "screen": "All screens",
            "component": "Brand and surface constraints",
            "ui_label": "Visuelle Leitplanken",
            "source_sheet": "README + Mockup_Constraints",
            "source_field": "DESIGN.md, entry_moment_situation_based_start.html, library_editorial_collection.html, method_detail_the_human_mirror.html, workshop_composer_session_flow.html, active_session_pro_facilitator_mode.html",
            "transformation_rule": "Aurora-Palette, Intentional Asymmetry, No-Line Rule, Gradient-CTA und Layering als UI-Systemregel anwenden.",
            "fallback_rule": "Bei kuenftigen Exporten nur die UI-Regeln angleichen; die kanonischen Inhalte bleiben in dieser SSOT verankert.",
            "notes": "Die Werte sind gegen DESIGN.md und die verfuegbaren HTML-Exporte verifiziert und duerfen nicht durch fiktive Mockup-Inhalte ersetzt werden.",
        },
    ]
    for item in items:
        rows.append([item[header] for header in UI_MAPPING_HEADERS])
    return rows


def build_readme_rows(raw_method_count: int) -> list[list[Any]]:
    rows = [README_HEADERS]
    entries = [
        ("Purpose", "Workbook role", "Diese Arbeitsmappe ist die kanonische SSOT fuer Method Finder, Library, Method Detail, Composer und Active Session."),
        ("Purpose", "Source hierarchy", "Fachlich verbindlich ist die reale Methodenliste aus dem Import. Stitch-/Brand-Dokumente steuern nur Produktlogik und UI-Constraints."),
        ("Purpose", "Method count", f"{raw_method_count} Methoden-Zeilen aus dem Import wurden uebernommen."),
        ("Source inputs", "Primary source", "Methodensammlung_KI.xlsx, Sheet Uebersicht."),
        ("Source inputs", "Design and mockup files used", "DESIGN.md sowie die HTML-Exporte fuer Entry Moment, Library Editorial Collection, Method Detail, Workshop Composer und Active Session wurden fuer Produktlogik-Alignment genutzt."),
        ("Source inputs", "Supporting product docs", "01_GOOGLE_STITCH_PROJECT_BRIEF.md, 02_STITCH_PROMPT_PACK.md, 03_STITCH_RUNBOOK.md, 04_STITCH_ONE_SHOT_PROMPT.txt und polarstern-brand-agent.md wurden zusaetzlich fuer Produkt- und Markenlogik beruecksichtigt."),
        ("Data classes", "Raw source", "RAW_Original_Import ist die archivierte Rohschicht. Sie bewahrt die originale Uebersicht inhaltlich unveraendert."),
        ("Data classes", "Normalized product layer", "Methods, Method_Tags, Vectors, Collections, Finder_Intents, Method_Variants und Composer_Blocks_Reference sind die normalisierte Produkt-Schicht."),
        ("Data classes", "Heuristic layer", "Energy/Intensity/Movement/Noise/Preparation sowie Teile von safeguarding_flag und indoor_outdoor sind Hilfsmetadaten. Ihre Herkunft steht in den *_source-Spalten der Methods-Tabelle."),
        ("Normalization rules", "Raw preservation", "RAW_Original_Import bewahrt den Import in inhaltlich unveraenderter Form als Archivschicht."),
        ("Normalization rules", "Method grain", "Methods enthaelt pro importierter Methoden-Zeile genau einen kanonischen Datensatz; erkennbare Dubletten wurden nicht still zusammengefuehrt."),
        ("Normalization rules", "Short descriptions", "Wenn die One-sentence-Spalte leer war, wurde short_description konservativ aus dem ersten Satz bzw. der ersten Zeile der Beschreibung extrahiert."),
        ("Normalization rules", "Primary purpose cleanup", "primary_purpose ist jetzt immer ein einzelnes dominantes Rohfragment. Wenn der Import mehrere Purpose-Signale enthielt, bleibt das erste Rohfragment im Feld und weitere Signale liegen in Method_Tags als purpose_signal."),
        ("Normalization rules", "Durations", "Dauer wurde nur befuellt, wenn im Import oder in Beschreibung/Notiz ein expliziter Wert stand. Einseitig bekannte Grenzen bleiben einseitig (z.B. ab 30 Min. oder bis 5 Min.). Alles andere bleibt leer."),
        ("Normalization rules", "Group sizes", "Gruppengroessen wurden nur bei klaren Angaben wie mind. 5 TN, 2-4 Personen oder 5-8 Personen normalisiert."),
        ("Normalization rules", "Controlled taxonomy", "Vectors, Finder_Intents, Collections und normalisierte Tags sind NEW_CONTROLLED_TAXONOMY und bewusst sparsam gehalten."),
        ("Normalization rules", "Provenance columns", "Methods.*_source markiert, ob ein Feld aus RAW_IMPORT, DESCRIPTION_EXPLICIT oder HEURISTIC_KEYWORD_MAPPING stammt."),
        ("Relations", "Method", "Methods ist die Kernentitaet fuer fachliche Inhalte."),
        ("Relations", "Tags and vectors", "Method_Tags und Method_Vector_Map liefern Browse-, Finder- und Filter-Signale."),
        ("Relations", "Collections", "Collections und Collection_Items bilden editoriale Gruppierungen fuer die Library."),
        ("Relations", "Variants", "Method_Variants werden nur verwendet, wenn die Quelle eine echte Unterform oder Einsatzvariante hergibt."),
        ("Relations", "Composer blocks", "Composer_Blocks_Reference liefert die pool-faehige Sicht fuer Drag-and-Drop, nicht die Runtime-Session selbst."),
        ("Authoritative use", "Frontend may treat as authoritative", "RAW_Original_Import als Archiv, Methods-Kernfelder (IDs, Name, Beschreibungen, primary_purpose, group_form, explizit belegte Dauer/Gruppengroesse), Method_Tags, Vectors, Collections, Method_Variants und UI_Field_Mapping."),
        ("Authoritative use", "Frontend must treat as optional", "Dauerchips, Gruppengroesse, Materialien, Facilitator Notes, Risk-/Safeguarding-Hinweise und heuristische Meta-Felder nur anzeigen, wenn das jeweilige Feld befuellt ist."),
        ("Authoritative use", "Heuristic fields in UI", "Felder mit *_source = HEURISTIC_KEYWORD_MAPPING sind Assistenzsignale fuer Browse/Composer und keine harten Rohfakten."),
        ("Consumption", "Method Finder", "Finder nutzt Finder_Intents als situation-first Einstiege und Method_Tags/Method_Vector_Map fuer zusaetzliche Suche."),
        ("Consumption", "Library", "Library list cards lesen primaer aus Methods; Collections und Vectors strukturieren Browse-Pfade."),
        ("Consumption", "Method Detail", "Method Detail zieht Kerninhalte aus Methods und optionale UI-spezifische Verfeinerungen aus Method_Variants."),
        ("Consumption", "Composer", "Composer nutzt Composer_Blocks_Reference als methoden- und variantenfaehigen Pool."),
        ("Consumption", "Active Session", "Active Session verbindet Methoden-/Variant-Basis mit Runtime-Timer, Session-Notizen und situativen Logs ausserhalb dieser SSOT."),
        ("Frontend constraints", "Palette and layout", "Aurora-Palette, Intentional Asymmetry und No-Line Rule sind Frontend-Vorgaben und gehoeren nicht als Inhalt in die Methoden."),
        ("Frontend constraints", "Typography", "Chau Philomene One nur fuer groessere editoriale Display-Momente; funktionale UI in Roboto."),
        ("Frontend constraints", "CTA and surfaces", "Gradient primary CTA sowie Surface-Layering bzw. Glass-Treatment nur als Designsystem-Regel verwenden."),
        ("Frontend constraints", "Duration visibility", "Duration chips, Karten-Metadaten und Timeline-Labels muessen verborgen bleiben, wenn keine grounded duration vorhanden ist."),
        ("Uncertainty handling", "Policy", "Unsichere Mappings wurden sichtbar markiert, nicht still geglaettet."),
        ("Cleanup v2.1", "Corrected factual notes", "README und Open_Questions wurden auf die verfuegbaren Design- und HTML-Dateien berichtigt."),
        ("Cleanup v2.1", "Purpose-field cleanup", "Mehrfach-Purpose-Werte wurden in einen singulaeren primary_purpose ueberfuehrt; weitere Signale liegen als purpose_signal in Method_Tags."),
        ("Cleanup v2.1", "Provenance clarification", "Methods enthaelt jetzt explizite *_source-Spalten fuer heuristische Produktfelder."),
        ("Cleanup v2.1", "Uncertainty updates", "Unsicherheit bleibt fuer tatsaechlich offene oder nur teilweise gestuetzte Planungswerte reserviert, vor allem bei Dauer, Dubletten und unvollstaendigen Datensaetzen."),
    ]
    for section, key, value in entries:
        rows.append([section, key, value])
    return rows


def build_raw_import_sheet(raw_rows: list[list[str]]) -> list[list[Any]]:
    out = [RAW_HEADERS]
    for row in raw_rows[1:]:
        values = [(value if clean_single_line(value) else "") for value in row[: len(RAW_HEADERS)]]
        out.append(values)
    return out


def build_vectors_sheet() -> list[list[Any]]:
    rows = [VECTOR_HEADERS]
    for vector in VECTOR_DEFINITIONS:
        rows.append([vector[header] for header in VECTOR_HEADERS])
    return rows


def build_mockup_constraints_sheet() -> list[list[Any]]:
    rows = [MOCKUP_CONSTRAINT_HEADERS]
    for item in MOCKUP_CONSTRAINTS:
        rows.append([item[header] for header in MOCKUP_CONSTRAINT_HEADERS])
    return rows


def build_open_questions_sheet() -> list[list[Any]]:
    rows = [OPEN_QUESTION_HEADERS]
    for item in OPEN_QUESTIONS:
        rows.append([item[header] for header in OPEN_QUESTION_HEADERS])
    return rows


def validate_sheet_headers(sheets: dict[str, list[list[Any]]]) -> None:
    expected = {
        "README": README_HEADERS,
        "RAW_Original_Import": RAW_HEADERS,
        "Methods": METHOD_HEADERS,
        "Method_Tags": METHOD_TAG_HEADERS,
        "Method_Variants": VARIANT_HEADERS,
        "Finder_Intents": FINDER_HEADERS,
        "Collections": COLLECTION_HEADERS,
        "Collection_Items": COLLECTION_ITEM_HEADERS,
        "Vectors": VECTOR_HEADERS,
        "Method_Vector_Map": METHOD_VECTOR_HEADERS,
        "Composer_Blocks_Reference": COMPOSER_HEADERS,
        "UI_Field_Mapping": UI_MAPPING_HEADERS,
        "Mockup_Constraints": MOCKUP_CONSTRAINT_HEADERS,
        "Open_Questions": OPEN_QUESTION_HEADERS,
    }
    for sheet_name, headers in expected.items():
        if sheet_name not in sheets:
            raise RuntimeError(f"Missing sheet {sheet_name}")
        actual = sheets[sheet_name][0]
        if actual != headers:
            raise RuntimeError(f"Header mismatch in {sheet_name}")


def split_id_list(value: str) -> list[str]:
    return [item.strip() for item in str(value).split(",") if item.strip()]


def validate_referential_integrity(
    method_index: dict[str, dict[str, Any]],
    variant_index: dict[str, dict[str, Any]],
    finder_rows: list[list[Any]],
    collection_rows: list[list[Any]],
    collection_item_rows: list[list[Any]],
    method_vector_rows: list[list[Any]],
    composer_rows: list[list[Any]],
) -> None:
    method_ids = set(method_index)
    variant_ids = set(variant_index)
    collection_ids = {row[0] for row in collection_rows[1:]}
    vector_ids = {item["vector_id"] for item in VECTOR_DEFINITIONS}

    for row in finder_rows[1:]:
        for source_id in split_id_list(row[8]):
            if source_id not in method_ids and source_id not in variant_ids:
                raise RuntimeError(f"Finder intent references unknown source id: {source_id}")

    for row in collection_item_rows[1:]:
        collection_id, source_id, item_type = row[0], row[1], row[2]
        if collection_id not in collection_ids:
            raise RuntimeError(f"Collection item references unknown collection id: {collection_id}")
        if item_type == "method" and source_id not in method_ids:
            raise RuntimeError(f"Collection item references unknown method id: {source_id}")
        if item_type == "variant" and source_id not in variant_ids:
            raise RuntimeError(f"Collection item references unknown variant id: {source_id}")

    for row in method_vector_rows[1:]:
        method_id, vector_id = row[0], row[1]
        if method_id not in method_ids:
            raise RuntimeError(f"Method_Vector_Map references unknown method id: {method_id}")
        if vector_id not in vector_ids:
            raise RuntimeError(f"Method_Vector_Map references unknown vector id: {vector_id}")

    for row in composer_rows[1:]:
        source_type, source_id, duration_value = row[1], row[2], row[4]
        if source_type == "method":
            if source_id not in method_ids:
                raise RuntimeError(f"Composer block references unknown method id: {source_id}")
            grounded = bool(method_index[source_id]["duration_min"] or method_index[source_id]["duration_max"])
        elif source_type == "variant":
            if source_id not in variant_ids:
                raise RuntimeError(f"Composer block references unknown variant id: {source_id}")
            variant = variant_index[source_id]
            method = method_index[variant["method_id"]]
            grounded = bool(variant["recommended_duration"] or method["duration_min"] or method["duration_max"])
        else:
            raise RuntimeError(f"Composer block has unknown source_type: {source_type}")
        if duration_value and not grounded:
            raise RuntimeError(f"Composer block has ungrounded duration_display: {source_id}")


def build_workbook(source_path: Path, output_path: Path) -> None:
    raw_rows, source_methods = load_source_methods(source_path)

    readme_rows = build_readme_rows(len(source_methods))
    raw_import_rows = build_raw_import_sheet(raw_rows)
    methods_rows, method_index = build_methods_sheet(source_methods)
    method_tags_rows, method_vector_rows, vector_map_labels = build_method_tags_and_vector_map(source_methods, method_index)
    variant_rows, variant_index = build_variants_sheet()
    finder_rows = build_finder_sheet()
    collections_rows = build_collections_sheet()
    collection_items_rows = build_collection_items(source_methods, method_index)
    vectors_rows = build_vectors_sheet()
    composer_rows = build_composer_reference(source_methods, method_index, variant_index, vector_map_labels)
    ui_mapping_rows = build_ui_field_mapping()
    mockup_constraint_rows = build_mockup_constraints_sheet()
    open_question_rows = build_open_questions_sheet()

    sheets = {
        "README": readme_rows,
        "RAW_Original_Import": raw_import_rows,
        "Methods": methods_rows,
        "Method_Tags": method_tags_rows,
        "Method_Variants": variant_rows,
        "Finder_Intents": finder_rows,
        "Collections": collections_rows,
        "Collection_Items": collection_items_rows,
        "Vectors": vectors_rows,
        "Method_Vector_Map": method_vector_rows,
        "Composer_Blocks_Reference": composer_rows,
        "UI_Field_Mapping": ui_mapping_rows,
        "Mockup_Constraints": mockup_constraint_rows,
        "Open_Questions": open_question_rows,
    }
    validate_sheet_headers(sheets)
    validate_referential_integrity(
        method_index=method_index,
        variant_index=variant_index,
        finder_rows=finder_rows,
        collection_rows=collections_rows,
        collection_item_rows=collection_items_rows,
        method_vector_rows=method_vector_rows,
        composer_rows=composer_rows,
    )

    writer = SimpleXlsxWriter()
    for name in [
        "README",
        "RAW_Original_Import",
        "Methods",
        "Method_Tags",
        "Method_Variants",
        "Finder_Intents",
        "Collections",
        "Collection_Items",
        "Vectors",
        "Method_Vector_Map",
        "Composer_Blocks_Reference",
        "UI_Field_Mapping",
        "Mockup_Constraints",
        "Open_Questions",
    ]:
        writer.add_sheet(name, sheets[name], freeze_header=True)
    writer.save(output_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Methodensammlung SSOT workbook.")
    parser.add_argument(
        "--source",
        default="Methodensammlung_KI.xlsx",
        help="Path to the source workbook.",
    )
    parser.add_argument(
        "--output",
        default="Methodensammlung_SSOT_v2_1.xlsx",
        help="Path to the generated workbook.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source_path = Path(args.source).resolve()
    output_path = Path(args.output).resolve()
    build_workbook(source_path, output_path)
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()

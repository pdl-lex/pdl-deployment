# import_tei_to_postgres.py
import asyncio
import asyncpg
import json
from lxml import etree
from pathlib import Path
from typing import Dict, List, Any
import sys
import xmltodict

# TEI Namespace
TEI_NS = {'tei': 'http://www.tei-c.org/ns/1.0'}

class TEIImporter:
    def __init__(self, db_url: str):
        self.db_url = db_url
        self.conn = None
        
    async def connect(self):
        """Verbindung zur Datenbank herstellen"""
        self.conn = await asyncpg.connect(self.db_url)
        print("✓ Connected to PostgreSQL")
        
    async def setup_schema(self):
        """Schema erstellen"""
        schema_sql = Path('schema.sql').read_text()
        await self.conn.execute(schema_sql)
        print("✓ Schema created/updated")
        
    async def close(self):
        """Verbindung schließen"""
        if self.conn:
            await self.conn.close()
            
    def extract_text_list(self, tree: etree._ElementTree, xpath: str) -> List[str]:
        """Extrahiere Liste von Texten via XPath"""
        return tree.xpath(xpath, namespaces=TEI_NS)
    
    def extract_text(self, tree: etree._ElementTree, xpath: str, default: str = '') -> str:
        """Extrahiere einzelnen Text via XPath"""
        results = tree.xpath(xpath, namespaces=TEI_NS)
        return results[0] if results else default
    
    def serialize_mixed_content(self, element: etree._Element) -> Dict[str, Any]:
        """
        Serialisiere ein XML-Element mit Mixed Content als positionserhaltende Struktur.
        
        Returns:
            {
                "content": [
                    {"type": "text", "value": "Text vor "},
                    {"type": "hi", "rend": "superscript", "value": "3"},
                    {"type": "text", "value": "Text nach"}
                ],
                "@type": "...",  # Attribute des Parent-Elements
                ...
            }
        """
        result = {}
        
        # Attribute übernehmen (ohne Namespace)
        for key, value in element.attrib.items():
            # Entferne TEI Namespace aus Attributnamen
            clean_key = key.replace('{http://www.tei-c.org/ns/1.0}', '')
            result[f"@{clean_key}"] = value
        
        # Prüfe ob Mixed Content vorliegt
        has_mixed = (element.text and element.text.strip()) or len(element) > 0
        
        if has_mixed:
            content = []
            
            # Text vor dem ersten Child
            if element.text and element.text.strip():
                content.append({
                    "type": "text",
                    "value": element.text
                })
            
            # Iteriere über Child-Elemente
            for child in element:
                # Child-Element
                child_tag = child.tag.replace('{http://www.tei-c.org/ns/1.0}', '')
                child_data = {
                    "type": child_tag,
                    "value": child.text or ""
                }
                
                # Child-Attribute
                for key, value in child.attrib.items():
                    clean_key = key.replace('{http://www.tei-c.org/ns/1.0}', '')
                    child_data[clean_key] = value
                
                content.append(child_data)
                
                # Text nach diesem Child (tail)
                if child.tail and child.tail.strip():
                    content.append({
                        "type": "text",
                        "value": child.tail
                    })
            
            result["content"] = content
        else:
            # Kein Mixed Content - nur Text
            result["value"] = element.text or ""
        
        return result

    def handle_mixed_content_elements(self, tree: etree._ElementTree) -> etree._ElementTree:
        """
        Identifiziere und markiere Elemente mit Mixed Content VOR der JSON-Konvertierung.
        Fügt ein temporäres Attribut 'mixed-content-json' mit der strukturierten Darstellung hinzu.
        """
        # Finde alle Elemente die Mixed Content haben könnten
        # Diese Liste kannst du erweitern je nachdem welche Elemente betroffen sind
        mixed_content_xpaths = [
            '//tei:note',
            '//tei:def',
            '//tei:quote',
            '//tei:cit',
            '//tei:bibl',
            '//tei:etym',
            '//tei:sense',
            # Weitere nach Bedarf...
        ]
        
        for xpath in mixed_content_xpaths:
            elements = tree.xpath(xpath, namespaces=TEI_NS)
            for elem in elements:
                # Prüfe ob wirklich Mixed Content (Text + Child-Elemente)
                has_text = elem.text and elem.text.strip()
                has_children = len(elem) > 0
                
                # Auch Kinder mit tail-Text zählen als Mixed Content
                has_tail = any(child.tail and child.tail.strip() for child in elem)
                
                if (has_text and has_children) or has_tail:
                    # Serialisiere als JSON und füge als Attribut ein
                    mixed_json = json.dumps(self.serialize_mixed_content(elem), ensure_ascii=False)
                    elem.set('mixed-content-json', mixed_json)
        
        return tree

    def clean_mixed_content_duplicates(self, data: Any) -> Any:
        """
        Entferne xmltodict-generierte Felder wenn 'content' Array existiert.
        """
        if isinstance(data, dict):
            # Wenn 'content' existiert, entferne die redundanten xmltodict-Felder
            if 'content' in data:
                # Lösche den leeren Key "" (xmltodict Text)
                data.pop('', None)
                
                # Lösche alle Child-Element Keys die jetzt in 'content' sind
                # (außer Attribute die mit @ beginnen)
                keys_to_remove = []
                for key in data.keys():
                    # Behalte nur: '@...', 'content', 'type'
                    if key not in ['content', 'type'] and not key.startswith('@'):
                        # Prüfe ob dieser Key ein Element ist das in content vorkommt
                        element_types = {item.get('type') for item in data['content'] if isinstance(item, dict)}
                        if key in element_types:
                            keys_to_remove.append(key)
                
                for key in keys_to_remove:
                    data.pop(key, None)
            
            # Rekursiv für alle Werte
            return {k: self.clean_mixed_content_duplicates(v) for k, v in data.items()}
        
        elif isinstance(data, list):
            return [self.clean_mixed_content_duplicates(item) for item in data]
        
        return data

    def extract_mixed_content_from_json(self, data: Any) -> Any:
        """
        Durchsuche JSON rekursiv und repariere Mixed Content Nodes.
        Nutzt das 'mixed-content-json' Attribut das wir vorher eingefügt haben.
        """
        if isinstance(data, dict):
            # Prüfe ob dieses Element Mixed Content hat
            if 'mixed-content-json' in data:
                try:
                    mixed_data = json.loads(data['mixed-content-json'])
                    # Merge die strukturierten Daten
                    data.update(mixed_data)
                    # Entferne das temporäre Attribut
                    del data['mixed-content-json']
                except json.JSONDecodeError:
                    pass
            
            # Rekursiv für alle Werte
            result = {k: self.extract_mixed_content_from_json(v) for k, v in data.items()}
            
            # Bereinige Duplikate NACHDEM alles verarbeitet wurde
            result = self.clean_mixed_content_duplicates(result)
            
            return result
        
        elif isinstance(data, list):
            return [self.extract_mixed_content_from_json(item) for item in data]
        
        return data
    
    def tei_to_json(self, tree: etree._ElementTree) -> Dict[str, Any]:
        """Konvertiere TEI XML zu JSON"""
        
        # SCHRITT 1: Mixed Content Elemente vorverarbeiten
        tree = self.handle_mixed_content_elements(tree)
        
        # SCHRITT 2: XML zu String und xmltodict
        xml_str = etree.tostring(tree, encoding='unicode')

        # XML Namespace-Attribute umbenennen
        xml_str = xml_str.replace('xml:id', 'xmlId').replace('xml:lang', 'xmlLang')
        
        # force_list: Diese Elemente sind IMMER Arrays
        data = xmltodict.parse(xml_str, attr_prefix="", cdata_key="", force_list={
            'form',
            'sense', 
            'cit',
            'usg',
            'ref',
            'bibl',
            'placeName',
            'note'
        })
        
        # SCHRITT 3: Mixed Content aus JSON extrahieren und bereinigen
        data = self.extract_mixed_content_from_json(data)
        
        return data
    
    def parse_tei_file(self, filepath: Path) -> Dict[str, Any]:
        """Parse ein TEI Lex-0 File und extrahiere alle relevanten Felder"""
        parser = etree.XMLParser(recover=True)  # Ignoriere XML-Fehler
        tree = etree.parse(str(filepath), parser)
                
        # ID extrahieren
        entry_id = self.extract_text(tree, '//tei:entry/@xml:id')
        if not entry_id:
            raise ValueError(f"No entry ID found in {filepath}")
        
        # Wörterbuch-Code
        wb = entry_id.split('__')[0] if '__' in entry_id else 'unknown'
        
        # Lemma
        lemma = self.extract_text(tree, '//tei:form[@type="lemma"]/tei:orth/text()')
        
        # Varianten
        variants = self.extract_text_list(tree, '//tei:form[@type="variant"]/tei:orth/text()')
        # Auch search forms hinzufügen
        variants.extend(self.extract_text_list(tree, '//tei:form[@type="search"]/tei:orth/text()'))
        variants = list(set(variants))  # Deduplizieren
        
        # Definitionen (alle sense/def)
        definitions = self.extract_text_list(tree, '//tei:sense/tei:def/text()')
        
        # Regionen
        regions = self.extract_text_list(tree, '//tei:usg[@type="geographic"]/text()')
        regions = list(set(regions))  # Deduplizieren
        
        # Vollständiges TEI als JSON
        tei_json = self.tei_to_json(tree)

        # Original TEI XML als String
        tei_xml = etree.tostring(tree, encoding='unicode', pretty_print=True)
        
        # Search Text (für Volltext-Suche)
        search_parts = [lemma] + variants + definitions
        # Auch Beispiele hinzufügen
        examples = self.extract_text_list(tree, '//tei:cit[@type="example"]/tei:quote/text()')
        search_parts.extend(examples[:5])  # Max 5 Beispiele
        search_text = ' '.join(search_parts)
        
        return {
            'id': entry_id,
            'wb': wb,
            'lemma': lemma,
            'lemma_variants': variants,
            'definitions': definitions,
            'regions': regions,
            'data': tei_json,
            'tei_xml': tei_xml,
            'search_text': search_text
        }
    
    async def import_file(self, filepath: Path) -> bool:
        """Importiere ein einzelnes TEI File"""
        try:
            data = self.parse_tei_file(filepath)
            
            await self.conn.execute("""
                INSERT INTO entries 
                (id, wb, lemma, lemma_variants, definitions, regions, data, tei_xml, search_text)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (id) DO UPDATE SET
                    wb = EXCLUDED.wb,
                    lemma = EXCLUDED.lemma,
                    lemma_variants = EXCLUDED.lemma_variants,
                    definitions = EXCLUDED.definitions,
                    regions = EXCLUDED.regions,
                    data = EXCLUDED.data,
                    tei_xml = EXCLUDED.tei_xml,
                    search_text = EXCLUDED.search_text,
                    updated_at = CURRENT_TIMESTAMP
            """, 
                data['id'],
                data['wb'],
                data['lemma'],
                data['lemma_variants'],
                data['definitions'],
                data['regions'],
                json.dumps(data['data']),
                data['tei_xml'],
                data['search_text']
            )
            return True
            
        except Exception as e:
            print(f"✗ Error importing {filepath.name}: {e}")
            return False
    
    async def import_batch(self, filepaths: List[Path]) -> tuple[int, int]:
        """Importiere mehrere Files als Batch"""
        batch_data = []
        failed = 0
        
        for filepath in filepaths:
            try:
                data = self.parse_tei_file(filepath)
                batch_data.append((
                    data['id'],
                    data['wb'],
                    data['lemma'],
                    data['lemma_variants'],
                    data['definitions'],
                    data['regions'],
                    json.dumps(data['data']),
                    data['tei_xml'],
                    data['search_text']
                ))
            except Exception as e:
                print(f"✗ Error parsing {filepath.name}: {e}")
                failed += 1
        
        if batch_data:
            await self.conn.executemany("""
                INSERT INTO entries 
                (id, wb, lemma, lemma_variants, definitions, regions, data, tei_xml, search_text)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (id) DO UPDATE SET
                    wb = EXCLUDED.wb,
                    lemma = EXCLUDED.lemma,
                    lemma_variants = EXCLUDED.lemma_variants,
                    definitions = EXCLUDED.definitions,
                    regions = EXCLUDED.regions,
                    data = EXCLUDED.data,
                    tei_xml = EXCLUDED.tei_xml,
                    search_text = EXCLUDED.search_text,
                    updated_at = CURRENT_TIMESTAMP
            """, batch_data)
        
        return len(batch_data), failed
    
    async def import_directory(self, directory: Path, batch_size: int = 1000):
        """Importiere alle TEI Files aus einem Verzeichnis"""
        tei_files = list(directory.glob('**/*.xml'))

        total = len(tei_files)
        
        if total == 0:
            print(f"✗ No XML files found in {directory}")
            return
        
        print(f"Found {total} TEI files to import")
        
        imported = 0
        failed = 0
        
        # Batch-Import
        for i in range(0, total, batch_size):
            batch = tei_files[i:i + batch_size]
            success, fail = await self.import_batch(batch)
            imported += success
            failed += fail
            
            print(f"Progress: {imported + failed}/{total} "
                  f"(✓ {imported}, ✗ {failed})")
        
        print(f"\n{'='*60}")
        print(f"Import complete!")
        print(f"  Total:    {total}")
        print(f"  Success:  {imported}")
        print(f"  Failed:   {failed}")
        print(f"{'='*60}")
        
        # Statistiken
        await self.print_statistics()
    
    async def print_statistics(self):
        """Zeige Statistiken über die importierten Daten"""
        stats = await self.conn.fetch("""
            SELECT 
                wb,
                COUNT(*) as entry_count,
                COUNT(DISTINCT lemma) as unique_lemmas,
                AVG(array_length(lemma_variants, 1)) as avg_variants,
                AVG(array_length(definitions, 1)) as avg_definitions
            FROM entries
            GROUP BY wb
            ORDER BY wb
        """)
        
        print("\nDatabase Statistics:")
        print(f"{'Dictionary':<15} {'Entries':<10} {'Unique':<10} {'Avg Vars':<10} {'Avg Defs':<10}")
        print("-" * 60)
        for row in stats:
            print(f"{row['wb']:<15} {row['entry_count']:<10} {row['unique_lemmas']:<10} "
                  f"{row['avg_variants'] or 0:<10.1f} {row['avg_definitions'] or 0:<10.1f}")
        
        total = await self.conn.fetchval("SELECT COUNT(*) FROM entries")
        print(f"\nTotal entries in database: {total}")


async def main():
    """Main Entry Point"""
    import argparse
    import os
    
    # Defaults from environment or fallback values
    default_user = os.getenv('POSTGRES_USER', 'postgres')
    default_password = os.getenv('POSTGRES_PASSWORD', 'postgres')
    default_db = os.getenv('POSTGRES_DB', 'wbdict')
    default_host = os.getenv('POSTGRES_HOST', 'localhost')
    default_port = os.getenv('POSTGRES_PORT', '5432')
    
    default_db_url = f'postgresql://{default_user}:{default_password}@{default_host}:{default_port}/{default_db}'
    
    parser = argparse.ArgumentParser(
        description='Import TEI Lex-0 files to PostgreSQL',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Beispiele:
  # Mit Umgebungsvariablen (empfohlen)
  export POSTGRES_USER=myuser
  export POSTGRES_PASSWORD=mypass
  export POSTGRES_DB=wbdict
  python {sys.argv[0]} /import/tei_files --setup-schema
  
  # Mit expliziter DB-URL
  python {sys.argv[0]} /import/tei_files \
    --db-url "postgresql://user:pass@localhost:5432/wbdict" \
    --setup-schema
  
  # Im Docker Container (mit docker-compose volumes)
  docker exec wb_postgres python /import/import_tei_to_postgres.py \
    /import/tei_files --setup-schema

Connection String Format:
  postgresql://USER:PASSWORD@HOST:PORT/DATABASE
  
Aktuelle Defaults (aus ENV oder Fallback):
  User:     {default_user}
  Host:     {default_host}
  Port:     {default_port}
  Database: {default_db}
  URL:      postgresql://{default_user}:***@{default_host}:{default_port}/{default_db}
        """
    )
    
    parser.add_argument('directory', type=str, 
                       help='Directory containing TEI XML files (z.B. /import/tei_files)')
    parser.add_argument('--db-url', type=str, 
                       default=default_db_url,
                       help=f'PostgreSQL connection URL (default: from ENV)')
    parser.add_argument('--db-host', type=str,
                       help='Database host (überschreibt ENV/URL)')
    parser.add_argument('--db-port', type=str,
                       help='Database port (überschreibt ENV/URL)')
    parser.add_argument('--db-user', type=str,
                       help='Database user (überschreibt ENV/URL)')
    parser.add_argument('--db-password', type=str,
                       help='Database password (überschreibt ENV/URL)')
    parser.add_argument('--db-name', type=str,
                       help='Database name (überschreibt ENV/URL)')
    parser.add_argument('--batch-size', type=int, default=1000,
                       help='Number of files to process in each batch')
    parser.add_argument('--setup-schema', action='store_true',
                       help='Create/update database schema before import')
    
    args = parser.parse_args()
    
    # Build DB URL from individual parameters if provided
    if any([args.db_host, args.db_port, args.db_user, args.db_password, args.db_name]):
        db_user = args.db_user or default_user
        db_password = args.db_password or default_password
        db_host = args.db_host or default_host
        db_port = args.db_port or default_port
        db_name = args.db_name or default_db
        db_url = f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'
    else:
        db_url = args.db_url
    
    directory = Path(args.directory)
    if not directory.exists():
        print(f"✗ Directory not found: {directory}")
        sys.exit(1)
    
    print(f"Connecting to: {db_url.split('@')[1] if '@' in db_url else db_url}")
    print(f"Import directory: {directory.absolute()}")
    print(f"{'='*60}")
    
    # Import
    importer = TEIImporter(db_url)
    
    try:
        await importer.connect()
        
        if args.setup_schema:
            await importer.setup_schema()
        
        await importer.import_directory(directory, args.batch_size)
        
    except Exception as e:
        print(f"✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        await importer.close()


if __name__ == '__main__':
    asyncio.run(main())
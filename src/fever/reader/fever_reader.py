import json
from overrides import overrides
from typing import Dict, Union, Iterable, List, Tuple

from allennlp.data import Tokenizer, TokenIndexer, Instance
from allennlp.data.dataset_readers.dataset_reader import DatasetReader
from allennlp.data.fields import TextField, LabelField
from allennlp.data.token_indexers import SingleIdTokenIndexer
from allennlp.data.tokenizers import WordTokenizer

from fever.reader.document_database import FEVERDocumentDatabase
from fever.reader.preprocessing import FEVERInstanceGenerator, ConcatenateEvidence
from fever.reader.simple_random import SimpleRandom




@DatasetReader.register("fever")
class FEVERDatasetReader(DatasetReader):
    
    def __init__(self, database: Union[FEVERDocumentDatabase, str],
                 wiki_tokenizer: Tokenizer = None,
                 claim_tokenizer: Tokenizer = None,
                 token_indexers: Dict[str, TokenIndexer] = None,
                 instance_generator: FEVERInstanceGenerator = None) -> None:

        super().__init__()
        if type(database) == str:
            database = FEVERDocumentDatabase(database)

        self._database = database
        self._wiki_tokenizer = wiki_tokenizer or WordTokenizer()
        self._claim_tokenizer = claim_tokenizer or WordTokenizer()
        self._token_indexers = token_indexers or {'tokens': SingleIdTokenIndexer()}
        self._instance_generator = instance_generator or ConcatenateEvidence()

    def get_doc_lines(self, page_title:str) -> List[str]:
        doc_lines = self._database.get_doc_lines(page_title)
        return [line.split('\t')[1] for line in doc_lines]

    def get_doc_line(self, page_title: str, line_number: int) -> str:
        if line_number is None:
            raise Exception("It looks like an NEI page is being loaded, but no evidence is present")

        if line_number > -1:
            return self.get_doc_lines(page_title)[line_number]
        else:
            return self.get_random_line(self.get_non_empty_lines(self.get_doc_lines(page_title)))

    def get_random_line(self,lines:List[str]) -> str:
        return lines[SimpleRandom.get_instance().next_rand(0, len(lines) - 1)]

    def get_non_empty_lines(self, lines:List[str]) -> List[str]:
        return [line for line in lines if len(line.strip())]

    @overrides
    def text_to_instance(self, evidence:str, claim:str, label:str = None) -> Instance:

        claim_tokens = self._claim_tokenizer.tokenize(claim)
        evidence_tokens = self._wiki_tokenizer.tokenize(evidence)

        instance_dict = {"premise": TextField(evidence_tokens, self._token_indexers),
                         "hypothesis": TextField(claim_tokens, self._token_indexers),
                        }


        if label is not None:
            instance_dict["label"] = LabelField(label)

        return Instance(instance_dict)


    def generate_instances(self,
                           evidence: List[List[Tuple[str,int]]],
                           claim: str,
                           label:str = None) -> Iterable[Instance]:

        generated = self._instance_generator.generate_instances(self, evidence, claim)
        return [self.text_to_instance(item['evidence'], item['claim'],label) for item in generated]

    """
    self.text_to_instance(evidence, claim)
    """

    @overrides
    def read(self, file_path:str) -> Iterable[Instance]:

        with open(file_path,"r") as f:
            for line in f:
                instance = json.loads(line)

                claim:str = instance['claim']
                evidence: List[List[Tuple[int,int,str,int]]] = instance['evidence']
                evidence: List[List[Tuple[str,int]]] = [[(item[2], item[3]) for item in group] for group in evidence]

                label:str = instance['label'] if 'label' in instance else None

                yield from self.generate_instances(evidence, claim, label)

from pydantic import BaseModel, Field


class Chunk(BaseModel):
    chunk_id: str = Field(description="Unique chunk id")
    doc_id: str = Field(description="Current uploaded document id")
    doc_type: str = Field(description="Document type: requirement/testcase")
    source_name: str = Field(description="Source file name")
    section_path: str = Field(description="Section path, e.g. ROOT > 登录 > 异常处理")
    paragraph_index: int = Field(description="Paragraph index within section content")
    text: str = Field(description="Chunk text")
    char_len: int = Field(description="Character length of chunk text")
    module: str = Field(default="", description="Optional module tag")
    test_type: str = Field(default="", description="Optional test type tag")
    priority: str = Field(default="", description="Optional priority tag")


class RetrievedChunk(BaseModel):
    chunk_id: str
    doc_id: str
    doc_type: str
    source_name: str
    section_path: str
    text: str
    score: float
    query: str


class Citation(BaseModel):
    chunk_id: str
    section_path: str
    source_name: str
    score: float

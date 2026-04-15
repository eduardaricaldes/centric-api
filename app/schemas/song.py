from pydantic import BaseModel

class SongBase(BaseModel):
    title:str
    artist:str| None = None
    lyrics:str| None = None

class SongCreate(SongBase):
    pass

class SongUpdate(BaseModel):
    title:str | None = None
    artist:str | None = None
    lyrics:str | None = None

class SongResponse(SongBase):
    id:int
    class Config:
        from_attributes = True


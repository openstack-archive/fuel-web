from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import Enum
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import UniqueConstraint

from nailgun.db.sqlalchemy.models.base import Base


class Tag(Base):
    __tablename__ = 'tags'
    __table_args__ = (
        UniqueConstraint('tag', 'owner_id', 'owner_type',
                         name='_tag_tag_uc'),
    )
    id = Column(Integer, primary_key=True)
    tag = Column(String(64), nullable=False)
    owner_id = Column(Integer, nullable=False)
    owner_type = Column(
        Enum(('release', 'cluster', 'plugin'), name='tag_owner_type'),
        nullable=False
    )
    has_primary = Column(Boolean)
    read_only = Column(Boolean)

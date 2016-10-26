from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import Enum
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import UniqueConstraint

from nailgun import consts
from nailgun.db.sqlalchemy.models.base import Base


class Tag(Base):
    __tablename__ = 'tags'
    __table_args__ = (
        UniqueConstraint('owner_type', 'owner_id', 'tag',
                         name='_tag_owner_uc'),
    )
    id = Column(Integer, primary_key=True)
    tag = Column(String(64), nullable=False)
    owner_id = Column(Integer, nullable=False)
    owner_type = Column(
        Enum(*consts.TAG_OWNER_TYPES, name='tag_owner_type'),
        nullable=False
    )
    has_primary = Column(Boolean, default=False)
    public_ip_required = Column(Boolean, default=False)
    public_for_dvr_required = Column(Boolean, default=False)
    read_only = Column(Boolean, default=False)

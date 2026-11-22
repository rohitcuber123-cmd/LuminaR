"""Digital-access facts are fresh Core evidence, never physical-stock inference."""
import re
from assistant.schemas import DigitalAvailability
from assistant.tools import ToolFailure


def digital_question(message):
    # A modality safety boundary on the user's request only, not a book resolver.
    # Reference identity and scope always come from the existing Qwen/resolver.
    text=message.casefold()
    format_term=r'(?:digital\s+(?:version|copy|edition|resource|access)|e[ -]?books?|pdf)'
    exists=rf'\b(?:has|have|there(?: is)?)\s+(?:(?:a|an|the|any|accessible|authorized)\s+)*{format_term}\b'
    access=r'\b(?:read|access|open|download|available|availability|accessible)\b'
    medium=rf'\b(?:{format_term}|online|digitally)\b'
    return bool(re.search(exists,text) or
        (re.search(access,text) and re.search(medium,text)) or
        re.search(r'\b(?:is|are)\b.{0,60}\bonline\s*\??$',text))


async def lookup(tools, book):
    catalogue=tools.catalogue
    library_id=getattr(catalogue,'library_id',None)
    path=(f'/libraries/{library_id}/catalogue/books/{book.work_id}/digital-availability'
          if library_id else f'/books/{book.work_id}/digital-availability')
    raw=await catalogue.transport.call('core','GET',path)
    try:
        result=DigitalAvailability.model_validate(raw)
        if result.work_id!=book.work_id or (str(result.library_id) if result.library_id else None)!=library_id:
            raise ValueError('Foreign digital evidence')
        return result
    except (ValueError,TypeError) as error:
        raise ToolFailure('core','INVALID_DIGITAL_EVIDENCE','Digital access could not be verified.') from error


def render(response):
    titles={b.work_id:b.title or b.work_id for b in response.books}
    statements=[]
    for item in response.digital_availability:
        title=titles[item.work_id]
        if item.status=='AUTHORIZED':
            kinds=', '.join(dict.fromkeys(r.asset_type for r in item.resources))
            statements.append(f'{title}: an authorized digital resource ({kinds}) is ready to open. Access is checked again when you open it.')
        else:
            statements.append(f'{title}: digital access cannot be verified for your account. A catalogue entry or physical copy does not establish online reading access.')
    return ' '.join(statements)

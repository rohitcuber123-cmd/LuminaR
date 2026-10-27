import {Link} from 'react-router-dom'
import {libraryBookPath} from '../lib/libraryWorkspace'
export function LibraryBookTitleLink({libraryId,bookId,staff=false,title,state}:{libraryId:string;bookId:string|null|undefined;staff?:boolean;title:string;state?:unknown}) {
  return bookId?<Link className="book-title-link" to={libraryBookPath(libraryId,bookId,staff)} state={state}>{title}</Link>:<>{title}</>
}

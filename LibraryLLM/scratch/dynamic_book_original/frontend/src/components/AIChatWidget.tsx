import {
  useState,
  type KeyboardEvent,
} from 'react'

import {
  BookOpen,
  MessageCircle,
  Search,
  Send,
  Sparkles,
  X,
} from 'lucide-react'


type ChatMessage = {
  id: number
  role: 'assistant' | 'user'
  text: string
}


const QUICK_ACTIONS = [
  {
    icon: Search,
    label: 'Find a book',
    prompt: 'Help me find a book.',
  },
  {
    icon: Sparkles,
    label: 'Recommend',
    prompt: 'Recommend something for me.',
  },
  {
    icon: BookOpen,
    label: 'Available now',
    prompt: 'Show me books available right now.',
  },
]


export function AIChatWidget() {
  const [open, setOpen] =
    useState(false)

  const [input, setInput] =
    useState('')

  const [messages, setMessages] =
    useState<ChatMessage[]>([
      {
        id: 1,
        role: 'assistant',
        text:
          'Welcome to LuminaR. I can help you discover books, explore subjects, check availability, and find your next read.',
      },
    ])


  function sendMessage(
    value?: string
  ) {
    const message =
      (value ?? input).trim()

    if (!message) return


    setMessages((previous) => [
      ...previous,

      {
        id: Date.now(),
        role: 'user',
        text: message,
      },
    ])


    setInput('')


    // FRONTEND MOCK RESPONSE ONLY

    window.setTimeout(() => {
      setMessages((previous) => [
        ...previous,

        {
          id: Date.now() + 1,
          role: 'assistant',

          text:
            'This is a frontend preview of LuminaR AI. Once connected to the library services, I’ll be able to help with search, recommendations, availability and more.',
        },
      ])
    }, 500)
  }


  function handleKeyDown(
    event:
      KeyboardEvent<HTMLInputElement>
  ) {
    if (event.key === 'Enter') {
      event.preventDefault()

      sendMessage()
    }
  }


  return (
    <>
      {/* =====================================================
          CHAT PANEL
      ===================================================== */}

      {open && (

        <div
          className="
            fixed
            bottom-24
            right-6
            z-[100]
            flex
            h-[570px]
            w-[390px]
            max-w-[calc(100vw-32px)]
            flex-col
            overflow-hidden
            border
            border-line
            bg-paper
            shadow-[0_24px_80px_rgba(24,20,16,0.18)]

            max-sm:
            bottom-4
            max-sm:right-4
            max-sm:h-[calc(100dvh-32px)]
            max-sm:w-[calc(100vw-32px)]
          "
        >

          {/* =================================================
              HEADER
          ================================================= */}

          <div
            className="
              shrink-0
              border-b
              border-line
              bg-paper
            "
          >

            {/* BRAND ACCENT */}

            <div
              className="
                h-[3px]
                w-full
                bg-brand
              "
            />


            <div
              className="
                flex
                items-center
                justify-between
                px-5
                py-4
              "
            >

              <div
                className="
                  flex
                  items-center
                  gap-3
                "
              >

                {/* AI ICON */}

                <div
                  className="
                    flex
                    h-10
                    w-10
                    items-center
                    justify-center
                    bg-brand
                    text-paper
                  "
                >

                  <Sparkles
                    className="
                      h-[18px]
                      w-[18px]
                    "
                    strokeWidth={1.6}
                  />

                </div>


                <div>

                  <div
                    className="
                      flex
                      items-center
                      gap-2
                    "
                  >

                    <h2
                      className="
                        font-display
                        text-[0.9rem]
                        uppercase
                        tracking-wide
                        text-ink
                      "
                    >
                      Lumina
                      <span
                        className="
                          text-brand
                        "
                      >
                        R
                      </span>
                      {' '}AI
                    </h2>


                    <span
                      className="
                        h-1.5
                        w-1.5
                        rounded-full
                        bg-brand
                      "
                    />

                  </div>


                  <p
                    className="
                      mt-0.5
                      text-[0.68rem]
                      uppercase
                      tracking-[0.12em]
                      text-ink-soft
                    "
                  >
                    Library Assistant
                  </p>

                </div>

              </div>


              {/* CLOSE */}

              <button
                onClick={() =>
                  setOpen(false)
                }

                aria-label="Close AI assistant"

                className="
                  flex
                  h-8
                  w-8
                  items-center
                  justify-center
                  text-ink-soft
                  transition
                  hover:bg-panel
                  hover:text-brand
                "
              >

                <X
                  className="
                    h-4
                    w-4
                  "
                />

              </button>

            </div>

          </div>



          {/* =================================================
              CHAT AREA
          ================================================= */}

          <div
            className="
              min-h-0
              flex-1
              overflow-y-auto
              px-5
              py-5
            "
          >

            {messages.map(
              (message) => (

                <div
                  key={message.id}

                  className={`
                    mb-5
                    flex

                    ${
                      message.role ===
                      'user'

                        ? 'justify-end'

                        : 'justify-start'
                    }
                  `}
                >

                  {message.role ===
                  'assistant' ? (

                    <div
                      className="
                        flex
                        max-w-[92%]
                        items-start
                        gap-3
                      "
                    >

                      {/* ASSISTANT AVATAR */}

                      <div
                        className="
                          mt-1
                          flex
                          h-8
                          w-8
                          shrink-0
                          items-center
                          justify-center
                          bg-brand
                          text-paper
                        "
                      >

                        <Sparkles
                          className="
                            h-3.5
                            w-3.5
                          "
                        />

                      </div>


                      <div>

                        <p
                          className="
                            mb-1.5
                            font-display
                            text-[0.58rem]
                            uppercase
                            tracking-[0.14em]
                            text-brand
                          "
                        >
                          LuminaR AI
                        </p>


                        <div
                          className="
                            border
                            border-line
                            bg-panel
                            px-4
                            py-3
                            text-[0.82rem]
                            leading-6
                            text-ink
                          "
                        >
                          {message.text}
                        </div>

                      </div>

                    </div>

                  ) : (

                    <div
                      className="
                        max-w-[82%]
                        bg-ink
                        px-4
                        py-3
                        text-[0.82rem]
                        leading-6
                        text-paper
                      "
                    >
                      {message.text}
                    </div>

                  )}

                </div>

              )
            )}



            {/* =================================================
                QUICK ACTIONS
            ================================================= */}

            {messages.length <= 1 && (

              <div
                className="
                  mt-7
                  border-t
                  border-line
                  pt-5
                "
              >

                <p
                  className="
                    mb-3
                    font-display
                    text-[0.6rem]
                    uppercase
                    tracking-[0.15em]
                    text-ink-soft
                  "
                >
                  Try asking
                </p>


                <div
                  className="
                    grid
                    gap-2
                  "
                >

                  {QUICK_ACTIONS.map(
                    (action) => {

                      const Icon =
                        action.icon

                      return (

                        <button
                          key={
                            action.label
                          }

                          onClick={() =>
                            sendMessage(
                              action.prompt
                            )
                          }

                          className="
                            group
                            flex
                            items-center
                            justify-between
                            border
                            border-line
                            bg-paper
                            px-3.5
                            py-3
                            text-left
                            transition
                            hover:border-brand
                            hover:bg-panel
                          "
                        >

                          <div
                            className="
                              flex
                              items-center
                              gap-3
                            "
                          >

                            <Icon
                              className="
                                h-4
                                w-4
                                text-brand
                              "
                              strokeWidth={1.6}
                            />


                            <span
                              className="
                                text-[0.76rem]
                                text-ink
                              "
                            >
                              {action.label}
                            </span>

                          </div>


                          <span
                            className="
                              text-sm
                              text-ink-soft
                              transition
                              group-hover:translate-x-1
                              group-hover:text-brand
                            "
                          >
                            →
                          </span>

                        </button>

                      )
                    }
                  )}

                </div>

              </div>

            )}

          </div>



          {/* =================================================
              INPUT AREA
          ================================================= */}

          <div
            className="
              shrink-0
              border-t
              border-line
              bg-paper
              p-4
            "
          >

            <div
              className="
                border
                border-line
                bg-panel
                transition
                focus-within:border-brand
              "
            >

              <input
                type="text"

                value={input}

                onChange={(event) =>
                  setInput(
                    event.target.value
                  )
                }

                onKeyDown={
                  handleKeyDown
                }

                placeholder="Ask LuminaR anything..."

                className="
                  h-12
                  w-full
                  bg-transparent
                  px-4
                  text-[0.8rem]
                  text-ink
                  outline-none
                  placeholder:text-ink-soft/60
                "
              />


              <div
                className="
                  flex
                  items-center
                  justify-between
                  border-t
                  border-line
                  px-2
                  py-2
                "
              >

                <span
                  className="
                    px-2
                    font-display
                    text-[0.56rem]
                    uppercase
                    tracking-[0.12em]
                    text-ink-soft/60
                  "
                >
                  Library Intelligence
                </span>


                <button
                  onClick={() =>
                    sendMessage()
                  }

                  disabled={
                    !input.trim()
                  }

                  aria-label="Send message"

                  className="
                    flex
                    h-9
                    w-9
                    items-center
                    justify-center
                    bg-brand
                    text-paper
                    transition
                    hover:opacity-90
                    disabled:cursor-not-allowed
                    disabled:opacity-30
                  "
                >

                  <Send
                    className="
                      h-3.5
                      w-3.5
                    "
                  />

                </button>

              </div>

            </div>

          </div>

        </div>

      )}



      {/* =====================================================
          FLOATING LAUNCH BUTTON
      ===================================================== */}

      {!open && (

        <button
          onClick={() =>
            setOpen(true)
          }

          aria-label="Open LuminaR AI"

          className="
            group
            fixed
            bottom-7
            right-7
            z-[100]
            flex
            items-center
            gap-3
            bg-brand
            px-4
            py-3
            text-paper
            shadow-[0_14px_35px_rgba(189,63,27,0.28)]
            transition
            duration-300
            hover:-translate-y-1
            hover:shadow-[0_18px_45px_rgba(189,63,27,0.36)]
          "
        >

          <div
            className="
              relative
              flex
              h-8
              w-8
              items-center
              justify-center
            "
          >

            <MessageCircle
              className="
                h-5
                w-5
              "
              strokeWidth={1.7}
            />


            <Sparkles
              className="
                absolute
                -right-1
                -top-1
                h-2.5
                w-2.5
              "
            />

          </div>


          <div
            className="
              hidden
              text-left
              sm:block
            "
          >

            <p
              className="
                font-display
                text-[0.65rem]
                uppercase
                tracking-[0.12em]
              "
            >
              Ask LuminaR
            </p>


            <p
              className="
                mt-0.5
                text-[0.58rem]
                opacity-70
              "
            >
              AI Library Assistant
            </p>

          </div>

        </button>

      )}

    </>
  )
}
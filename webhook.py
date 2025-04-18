import argparse
import asyncio
from flask import Flask, request, redirect
import logging
import nats
import os
from pydantic import BaseModel
from twilio.twiml.messaging_response import MessagingResponse

class Message(BaseModel):
    from_number: str
    body: str

app = Flask(__name__)

@app.route("/sms", methods=['GET', 'POST'])
async def sms_reply():
    """Push SMS message to NATS and respond with an acknowledgment."""

    from_number = request.values.get('From', None)
    if from_number not in app.config['ALLOWED_NUMBERS']:
        logging.warning(f"Received message from unauthorized number: {from_number}")
        return "Unauthorized", 403

    body = request.values.get('Body', None)
    logging.info(f"Received message from {from_number}")

    # Publish the message to NATS
    subject = app.config['NATS_SUBJECT']
    nc = await nats.connect(app.config['NATS_URL'])
    data = Message(from_number=from_number, body=body)
    logging.debug(f"Publishing message to NATS: {subject} {data}")
    await nc.publish(subject, data.model_dump_json().encode('utf-8'))
    await nc.flush()
    await nc.close()

    # Start our TwiML response
    resp = MessagingResponse()

    # Add a message
    resp.message(f"Got it!")

    return str(resp)

async def main():
    default_nats_server = os.getenv("NATS_SERVER", "nats://localhost:4222")

    parser = argparse.ArgumentParser(description='Webhook for Twilio SMS',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--port', type=int, default=5000, help='Port to run the webhook on')
    parser.add_argument('--allowed-numbers', required=True, nargs='+', help='List of allowed phone numbers')
    parser.add_argument('--nats-url', type=str, help='NATS server URL',
                        default=default_nats_server)
    parser.add_argument('--nats-subject', type=str, help='NATS subject to publish messages to',
                        default='sms.message')
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    app.config['ALLOWED_NUMBERS'] = set(args.allowed_numbers)
    app.config['NATS_URL'] = args.nats_url
    app.config['NATS_SUBJECT'] = args.nats_subject

    app.run(host="127.0.0.1", port=args.port, debug=args.debug)

if __name__ == "__main__":
    asyncio.run(main())

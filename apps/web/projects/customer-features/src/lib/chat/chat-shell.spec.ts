import { provideHttpClient } from '@angular/common/http';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { PLATFORM_API_CONFIG } from 'platform-core';
import { ChatShell } from './chat-shell';

describe('ChatShell', () => {
  let fixture: ComponentFixture<ChatShell>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ChatShell],
      providers: [
        provideHttpClient(),
        {
          provide: PLATFORM_API_CONFIG,
          useValue: {
            gatewayOrigin: 'https://api.test.example',
            authAuthority: 'https://login.microsoftonline.com',
            authClientId: 'client-id',
            authScopes: [],
          },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(ChatShell);
    fixture.detectChanges();
  });

  it('renders', () => {
    expect(fixture.componentInstance).toBeTruthy();
  });

  it('exposes a labelled landmark', () => {
    const section = fixture.nativeElement.querySelector('section');
    expect(section?.getAttribute('aria-labelledby')).toBe('cf-chat-heading');
  });

  it('starts idle rather than claiming an empty conversation', () => {
    expect(fixture.componentInstance['messages']().status).toBe('idle');
  });
});

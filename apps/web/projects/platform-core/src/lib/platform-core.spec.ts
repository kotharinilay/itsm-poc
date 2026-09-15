import { ComponentFixture, TestBed } from '@angular/core/testing';

import { PlatformCore } from './platform-core';

describe('PlatformCore', () => {
  let component: PlatformCore;
  let fixture: ComponentFixture<PlatformCore>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [PlatformCore],
    }).compileComponents();

    fixture = TestBed.createComponent(PlatformCore);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
